package com.enterprise.modernization.rewrite;

import com.enterprise.modernization.rewrite.model.ClassRecord;
import com.enterprise.modernization.rewrite.model.FieldRecord;
import com.enterprise.modernization.rewrite.model.InvocationRecord;
import com.enterprise.modernization.rewrite.model.MethodRecord;
import org.openrewrite.ExecutionContext;
import org.openrewrite.Recipe;
import org.openrewrite.TreeVisitor;
import org.openrewrite.java.JavaIsoVisitor;
import org.openrewrite.java.tree.J;
import org.openrewrite.java.tree.JavaType;
import org.openrewrite.java.tree.Statement;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.stream.Collectors;

/**
 * OpenRewrite Recipe that traverses the Lossless Semantic Tree (LST) of a legacy Java EE codebase
 * and extracts structured metadata for graph ingestion (Step 2).
 *
 * <p>Extracts:
 * <ul>
 *   <li>Class/Interface declarations: FQN, kind, annotations</li>
 *   <li>Field injections: @EJB, @Inject, @Autowired, @PersistenceContext, @Resource</li>
 *   <li>Method declarations: name, return type, parameter signatures, annotations</li>
 *   <li>Method invocations: caller class/method → target class/method with type attribution</li>
 * </ul>
 *
 * <p>All type resolution is null-safe. Unresolvable types (JavaType.Unknown or null)
 * fall back to AST text representations rather than throwing NullPointerException.
 */
public class LegacyMetadataExtractor extends Recipe {

    private static final Logger log = LoggerFactory.getLogger(LegacyMetadataExtractor.class);

    /**
     * Thread-safe accumulator shared across all source files processed by the visitor.
     * Uses CopyOnWriteArrayList so visitor output can be read safely after processing.
     */
    private final List<ClassRecord> classRecords = new CopyOnWriteArrayList<>();

    @Override
    public String getDisplayName() {
        return "Legacy Java EE Metadata Extractor";
    }

    @Override
    public String getDescription() {
        return "Extracts class declarations, field injections, method declarations, and " +
               "method invocations from Java EE 6 / JSF LSTs for graph ingestion.";
    }

    /** Returns immutable view of accumulated class records after extraction is complete. */
    public List<ClassRecord> getClassRecords() {
        return Collections.unmodifiableList(classRecords);
    }

    @Override
    public TreeVisitor<?, ExecutionContext> getVisitor() {
        return new MetadataVisitor(classRecords);
    }

    // =========================================================================
    // Inner Visitor
    // =========================================================================

    private static final class MetadataVisitor extends JavaIsoVisitor<ExecutionContext> {

        private static final Set<String> INJECTION_ANNOTATIONS = Set.of(
            "Inject", "EJB", "Autowired", "PersistenceContext", "Resource"
        );

        /**
         * Shared accumulator passed in from the Recipe (closure pattern).
         * New records are added here as each source file's class declarations are visited.
         */
        private final List<ClassRecord> accumulator;

        /**
         * Per-visitor-session in-progress map.
         * Maps class FQN → ClassRecord currently being built, so that nested visitors
         * (visitMethodDeclaration, visitMethodInvocation) can locate and update the
         * correct ClassRecord without re-traversing.
         */
        private final Map<String, ClassRecord> inProgress = new ConcurrentHashMap<>();

        MetadataVisitor(List<ClassRecord> accumulator) {
            this.accumulator = accumulator;
        }

        // =====================================================================
        // Class Declaration
        // =====================================================================

        @Override
        public J.ClassDeclaration visitClassDeclaration(J.ClassDeclaration cd, ExecutionContext ctx) {
            String fqn        = resolveClassFqn(cd);
            String simpleName = cd.getSimpleName();
            String kind       = cd.getKind().name().toUpperCase(Locale.ROOT);

            List<String> annotations = cd.getLeadingAnnotations().stream()
                .map(J.Annotation::getSimpleName)
                .collect(Collectors.toList());

            // Extract field injections before descending into methods
            List<FieldRecord> fields = extractFieldInjections(cd);

            ClassRecord record = new ClassRecord(
                fqn, simpleName, kind, annotations, fields,
                new ArrayList<>(),   // methods — populated in visitMethodDeclaration
                new ArrayList<>()    // invocations — populated in visitMethodInvocation
            );

            // Register in in-progress map BEFORE calling super so that nested
            // visitMethodDeclaration / visitMethodInvocation can find this record.
            inProgress.put(fqn, record);

            // Recurse into class body (triggers visitMethodDeclaration and visitMethodInvocation)
            J.ClassDeclaration result = super.visitClassDeclaration(cd, ctx);

            // Finalize: move from in-progress to the shared accumulator
            inProgress.remove(fqn);
            accumulator.add(record);

            log.debug("[Extractor] Class extracted: {} ({} methods, {} invocations)",
                fqn, record.getMethods().size(), record.getInvocations().size());

            return result;
        }

        // =====================================================================
        // Method Declaration
        // =====================================================================

        @Override
        public J.MethodDeclaration visitMethodDeclaration(J.MethodDeclaration md, ExecutionContext ctx) {
            // Let super visit the method body first (triggers visitMethodInvocation for calls inside)
            J.MethodDeclaration result = super.visitMethodDeclaration(md, ctx);

            try {
                J.ClassDeclaration enclosingClass = getCursor().firstEnclosing(J.ClassDeclaration.class);
                if (enclosingClass == null) return result;

                String classFqn = resolveClassFqn(enclosingClass);
                ClassRecord classRecord = inProgress.get(classFqn);
                if (classRecord == null) return result;

                String methodName = md.getSimpleName();

                // Return type — guard against null (constructors have null return type expression)
                String returnType = "void";
                if (md.getReturnTypeExpression() != null) {
                    // Prefer resolved type; fall back to AST text
                    JavaType.Method mt = md.getMethodType();
                    returnType = resolveType(
                        mt != null ? mt.getReturnType() : null,
                        md.getReturnTypeExpression().toString()
                    );
                }

                // Parameter types
                List<String> paramTypes = md.getParameters().stream()
                    .filter(p -> p instanceof J.VariableDeclarations)
                    .map(p -> {
                        J.VariableDeclarations vd = (J.VariableDeclarations) p;
                        return resolveType(vd.getType(),
                            vd.getTypeExpression() != null ? vd.getTypeExpression().toString() : "Object");
                    })
                    .collect(Collectors.toList());

                // Method-level annotations
                List<String> methodAnnotations = md.getLeadingAnnotations().stream()
                    .map(J.Annotation::getSimpleName)
                    .collect(Collectors.toList());

                String signature = buildMethodSignature(classFqn, methodName, paramTypes);

                // Extract method execution details: bodySource, thrownExceptions, branchCount
                List<String> thrownExceptions = new ArrayList<>();
                int[] branchCount = new int[1];
                String bodySource = null;

                if (md.getBody() != null) {
                    if (!isTrivialAccessor(md)) {
                        bodySource = md.getBody().printTrimmed(getCursor());
                    }

                    new JavaIsoVisitor<ExecutionContext>() {
                        @Override
                        public J.Throw visitThrow(J.Throw thrown, ExecutionContext ctx) {
                            if (thrown.getException() instanceof J.NewClass) {
                                J.NewClass nc = (J.NewClass) thrown.getException();
                                if (nc.getClazz() != null) {
                                    thrownExceptions.add(nc.getClazz().toString());
                                }
                            } else if (thrown.getException() != null) {
                                thrownExceptions.add(thrown.getException().toString());
                            }
                            return super.visitThrow(thrown, ctx);
                        }

                        @Override
                        public J.If visitIf(J.If iff, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitIf(iff, ctx);
                        }

                        @Override
                        public J.WhileLoop visitWhileLoop(J.WhileLoop whileLoop, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitWhileLoop(whileLoop, ctx);
                        }

                        @Override
                        public J.ForLoop visitForLoop(J.ForLoop forLoop, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitForLoop(forLoop, ctx);
                        }

                        @Override
                        public J.ForEachLoop visitForEachLoop(J.ForEachLoop forEachLoop, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitForEachLoop(forEachLoop, ctx);
                        }

                        @Override
                        public J.Case visitCase(J.Case _case, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitCase(_case, ctx);
                        }

                        @Override
                        public J.Ternary visitTernary(J.Ternary ternary, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitTernary(ternary, ctx);
                        }

                        @Override
                        public J.Try.Catch visitCatch(J.Try.Catch _catch, ExecutionContext ctx) {
                            branchCount[0]++;
                            return super.visitCatch(_catch, ctx);
                        }
                    }.visit(md.getBody(), ctx);
                }

                List<String> uniqueThrown = thrownExceptions.stream().distinct().collect(Collectors.toList());

                classRecord.getMethods().add(
                    new MethodRecord(
                        methodName, returnType, paramTypes, methodAnnotations,
                        signature, uniqueThrown, branchCount[0], bodySource
                    )
                );

            } catch (Exception e) {
                log.debug("[Extractor] Non-fatal: could not extract method metadata — {}", e.getMessage());
            }

            return result;
        }

        private boolean isTrivialAccessor(J.MethodDeclaration md) {
            if (md.getBody() == null || md.getBody().getStatements() == null) return true;
            String name = md.getSimpleName();
            int stmtCount = md.getBody().getStatements().size();
            if (stmtCount <= 1) {
                if ((name.startsWith("get") || name.startsWith("is"))
                    && (md.getParameters().isEmpty() || (md.getParameters().size() == 1 && md.getParameters().get(0) instanceof J.Empty))) {
                    return true;
                }
                if (name.startsWith("set") && md.getParameters().size() == 1) {
                    return true;
                }
            }
            return false;
        }

        // =====================================================================
        // Method Invocation (Call Graph Extraction)
        // =====================================================================

        @Override
        public J.MethodInvocation visitMethodInvocation(J.MethodInvocation mi, ExecutionContext ctx) {
            J.MethodInvocation result = super.visitMethodInvocation(mi, ctx);

            try {
                // Identify the class in whose context this call appears
                J.ClassDeclaration enclosingClass = getCursor().firstEnclosing(J.ClassDeclaration.class);
                if (enclosingClass == null) return result;

                String callerClassFqn = resolveClassFqn(enclosingClass);
                ClassRecord classRecord = inProgress.get(callerClassFqn);
                if (classRecord == null) return result;

                // Enclosing method may be null (e.g., field initializer or static block)
                J.MethodDeclaration enclosingMethod = getCursor().firstEnclosing(J.MethodDeclaration.class);
                String callerMethodName = enclosingMethod != null
                    ? enclosingMethod.getSimpleName()
                    : "<static_init>";

                // Resolved method type — null when the target type is not on the classpath
                JavaType.Method methodType = mi.getMethodType();
                if (methodType == null) {
                    // Graceful degradation: record a partial invocation using AST text
                    String targetMethodName = mi.getSimpleName();
                    classRecord.getInvocations().add(new InvocationRecord(
                        callerClassFqn, callerMethodName,
                        "<unresolved>", targetMethodName,
                        "Object", Collections.emptyList()
                    ));
                    return result;
                }

                // Resolve target class FQN
                String targetClassFqn;
                JavaType.FullyQualified declaringType = methodType.getDeclaringType();
                if (declaringType != null) {
                    targetClassFqn = declaringType.getFullyQualifiedName();
                } else {
                    // Fall back: use caller FQN prefix + method name (best effort)
                    targetClassFqn = "<unresolved>." + mi.getSimpleName();
                }

                String targetMethodName = methodType.getName();
                String returnType       = resolveType(methodType.getReturnType(), "void");

                List<String> argTypes = methodType.getParameterTypes().stream()
                    .map(pt -> resolveType(pt, "Object"))
                    .collect(Collectors.toList());

                // Skip self-referential invocations (reduces graph noise)
                if (targetClassFqn.equals(callerClassFqn)) return result;

                classRecord.getInvocations().add(new InvocationRecord(
                    callerClassFqn, callerMethodName,
                    targetClassFqn, targetMethodName,
                    returnType, argTypes
                ));

            } catch (Exception e) {
                log.debug("[Extractor] Non-fatal: could not extract invocation metadata — {}", e.getMessage());
            }

            return result;
        }

        // =====================================================================
        // Field Injection Extraction Helper
        // =====================================================================

        private List<FieldRecord> extractFieldInjections(J.ClassDeclaration cd) {
            if (cd.getBody() == null) return Collections.emptyList();

            List<FieldRecord> fields = new ArrayList<>();

            for (Statement stmt : cd.getBody().getStatements()) {
                if (!(stmt instanceof J.VariableDeclarations vd)) continue;

                // Find the first injection annotation on this field declaration
                String injectionAnnotation = null;
                for (J.Annotation ann : vd.getLeadingAnnotations()) {
                    if (INJECTION_ANNOTATIONS.contains(ann.getSimpleName())) {
                        injectionAnnotation = ann.getSimpleName();
                        break;
                    }
                }
                if (injectionAnnotation == null) continue;

                // Simple type name (from AST text — always available)
                String typeName = vd.getTypeExpression() != null
                    ? vd.getTypeExpression().toString()
                    : "Object";

                // Fully qualified type name (from resolved type — may be null for missing classpath JARs)
                String typeFqn = vd.getType() instanceof JavaType.FullyQualified fq
                    ? fq.getFullyQualifiedName()
                    : null;

                for (J.VariableDeclarations.NamedVariable var : vd.getVariables()) {
                    fields.add(new FieldRecord(var.getSimpleName(), typeName, typeFqn, injectionAnnotation));
                }
            }

            return fields;
        }

        // =====================================================================
        // Type Resolution Helpers (Null-Safe)
        // =====================================================================

        /**
         * Resolves a {@link JavaType} to its string representation, falling back to
         * {@code fallback} when the type is null, Unknown, or a non-FQN type.
         */
        private String resolveType(JavaType type, String fallback) {
            if (type instanceof JavaType.FullyQualified fq) {
                return fq.getFullyQualifiedName();
            }
            if (type instanceof JavaType.Primitive p) {
                return p.getKeyword();
            }
            if (type instanceof JavaType.Array arr) {
                return resolveType(arr.getElemType(), "Object") + "[]";
            }
            if (type instanceof JavaType.Parameterized pt) {
                // e.g. List<Account> → java.util.List
                return resolveType(pt.getType(), fallback);
            }
            // JavaType.Unknown, JavaType.GenericTypeVariable, null → use fallback
            return fallback != null ? fallback : "Object";
        }

        /** Returns FQN of class declaration, falling back to package declaration + simple name if type is unresolved. */
        private String resolveClassFqn(J.ClassDeclaration cd) {
            JavaType.FullyQualified fq = cd.getType();
            if (fq != null && fq.getFullyQualifiedName() != null && !fq.getFullyQualifiedName().isEmpty()) {
                return fq.getFullyQualifiedName();
            }
            // Fall back to package declaration + simple name
            J.CompilationUnit cu = getCursor().firstEnclosing(J.CompilationUnit.class);
            if (cu != null && cu.getPackageDeclaration() != null) {
                String pkg = cu.getPackageDeclaration().getExpression().printTrimmed(getCursor());
                return pkg + "." + cd.getSimpleName();
            }
            return cd.getSimpleName();
        }

        /** Builds a canonical method signature string: {@code com.example.Foo.bar(int,String)}. */
        private String buildMethodSignature(String classFqn, String methodName, List<String> paramTypes) {
            return classFqn + "." + methodName + "(" + String.join(",", paramTypes) + ")";
        }
    }
}
