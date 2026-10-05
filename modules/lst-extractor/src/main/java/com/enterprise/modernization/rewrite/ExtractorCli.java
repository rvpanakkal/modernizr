package com.enterprise.modernization.rewrite;

import com.enterprise.modernization.rewrite.model.ClassRecord;
import com.enterprise.modernization.rewrite.model.LSTExportPayload;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.openrewrite.InMemoryExecutionContext;
import org.openrewrite.java.JavaParser;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * CLI entry point for the LST Metadata Extractor (Pipeline Step 1).
 *
 * <p>Usage:
 * <pre>
 *   java -jar lst-extractor.jar \
 *     --source-dir samples/legacy-banking-monolith/src/main/java \
 *     --output artifacts/raw_lst/metadata_extracted.json
 * </pre>
 *
 * <p>Graceful degradation behaviour:
 * <ul>
 *   <li>Missing classpath JARs (Java EE, Jakarta EE) do NOT halt execution.</li>
 *   <li>Type-resolution failures are logged as WARN and the affected type
 *       falls back to its AST text representation.</li>
 *   <li>Source files that cannot be parsed are skipped with an error log entry.</li>
 * </ul>
 */
@Command(
    name        = "lst-extractor",
    description = "Extracts Lossless Semantic Tree (LST) metadata from a legacy Java EE " +
                  "source directory and writes structured JSON for Neo4j graph ingestion.",
    mixinStandardHelpOptions = true,
    version     = "1.0.0"
)
public class ExtractorCli implements Callable<Integer> {

    private static final Logger log = LoggerFactory.getLogger(ExtractorCli.class);

    @Option(
        names       = {"--source-dir", "-s"},
        description = "Root directory containing the legacy Java source files to analyse.",
        defaultValue = "./src"
    )
    private File sourceDir;

    @Option(
        names       = {"--output", "-o"},
        description = "Output path for the extracted metadata JSON file.",
        defaultValue = "artifacts/raw_lst/metadata_extracted.json"
    )
    private File outputFile;

    // =========================================================================
    // Main
    // =========================================================================

    public static void main(String[] args) {
        int exitCode = new CommandLine(new ExtractorCli()).execute(args);
        System.exit(exitCode);
    }

    // =========================================================================
    // Execution
    // =========================================================================

    @Override
    public Integer call() {
        log.info("[LST Extractor] ── Step 1: LST Extraction ───────────────────────────");
        log.info("[LST Extractor] Source directory : {}", sourceDir.getAbsolutePath());
        log.info("[LST Extractor] Output file      : {}", outputFile.getAbsolutePath());

        if (!sourceDir.exists() || !sourceDir.isDirectory()) {
            log.error("[LST Extractor] Source directory does not exist or is not a directory: {}",
                sourceDir.getAbsolutePath());
            return 1;
        }

        // ── 1. Discover all .java files ───────────────────────────────────────
        List<Path> javaFiles = discoverJavaFiles(sourceDir.toPath());
        if (javaFiles.isEmpty()) {
            log.warn("[LST Extractor] No .java files found under: {}", sourceDir.getAbsolutePath());
        }
        log.info("[LST Extractor] Discovered {} Java source files.", javaFiles.size());

        // ── 2. Build execution context with graceful error handling ───────────
        //
        // InMemoryExecutionContext captures type-resolution warnings without aborting.
        // Legacy EE JARs (javax.faces, javax.ejb, javax.persistence) are typically
        // absent from the classpath at analysis time; we log and continue.
        InMemoryExecutionContext ctx = new InMemoryExecutionContext(throwable -> {
            String msg = throwable.getMessage();
            // Suppress overly verbose "Could not resolve type" noise at DEBUG level
            if (msg != null && msg.contains("Could not resolve type")) {
                log.debug("[LST Extractor] Type resolution (degraded): {}", msg);
            } else {
                log.warn("[LST Extractor] Non-fatal extraction warning: {}", msg);
            }
        });

        // ── 3. Build JavaParser ───────────────────────────────────────────────
        //
        // We do NOT add legacy EE JARs to the classpath deliberately.
        // OpenRewrite handles unresolved types as JavaType.Unknown, which our
        // visitor converts to safe text fallbacks instead of throwing NPEs.
        JavaParser javaParser = JavaParser.fromJavaVersion()
            .logCompilationWarningsAndErrors(false) // suppress compile warnings to stderr
            .build();

        // ── 4. Instantiate recipe and run visitor ─────────────────────────────
        LegacyMetadataExtractor extractor = new LegacyMetadataExtractor();

        if (!javaFiles.isEmpty()) {
            try {
                log.info("[LST Extractor] Parsing source files …");
                javaParser.parse(javaFiles, sourceDir.toPath(), ctx)
                    .forEach(cu -> {
                        try {
                            extractor.getVisitor().visit(cu, ctx);
                        } catch (Exception e) {
                            log.error("[LST Extractor] Failed to visit compilation unit: {}", e.getMessage(), e);
                        }
                    });
            } catch (Exception e) {
                log.error("[LST Extractor] JavaParser encountered a fatal error: {}", e.getMessage(), e);
                return 1;
            }
        }

        // ── 5. Assemble output payload ────────────────────────────────────────
        List<ClassRecord> classes = extractor.getClassRecords();
        LSTExportPayload payload  = new LSTExportPayload(
            Instant.now().toString(),
            sourceDir.getAbsolutePath(),
            classes
        );

        log.info("[LST Extractor] Extracted {} class records.", classes.size());

        // ── 6. Serialize to JSON ──────────────────────────────────────────────
        try {
            writeJson(payload, outputFile);
        } catch (IOException e) {
            log.error("[LST Extractor] Failed to write output JSON: {}", e.getMessage(), e);
            return 1;
        }

        log.info("[LST Extractor] ✓ Metadata written to: {}", outputFile.getAbsolutePath());
        log.info("[LST Extractor] ── Step 1 Complete ──────────────────────────────────");
        return 0;
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    /**
     * Recursively discovers all {@code .java} files under the given root directory.
     * Files that cannot be read are silently skipped.
     */
    private static List<Path> discoverJavaFiles(Path root) {
        try (Stream<Path> stream = Files.walk(root)) {
            return stream
                .filter(Files::isRegularFile)
                .filter(p -> p.getFileName().toString().endsWith(".java"))
                .sorted()
                .collect(Collectors.toList());
        } catch (IOException e) {
            log.error("[LST Extractor] Error walking source directory: {}", e.getMessage(), e);
            return List.of();
        }
    }

    /**
     * Serialises the {@link LSTExportPayload} to a pretty-printed JSON file,
     * creating any missing parent directories.
     */
    private static void writeJson(LSTExportPayload payload, File outputFile) throws IOException {
        File parent = outputFile.getParentFile();
        if (parent != null && !parent.exists()) {
            if (!parent.mkdirs()) {
                throw new IOException("Could not create output directory: " + parent.getAbsolutePath());
            }
        }

        ObjectMapper mapper = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .enable(SerializationFeature.INDENT_OUTPUT)
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

        mapper.writeValue(outputFile, payload);
    }
}
