package com.enterprise.modernization.rewrite.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

import java.util.ArrayList;
import java.util.List;

/**
 * Represents a single Java class or interface extracted from the LST.
 */
@JsonPropertyOrder({"fqn", "simpleName", "kind", "annotations", "fields", "methods", "invocations"})
public class ClassRecord {

    @JsonProperty("fqn")
    private String fqn;

    @JsonProperty("simpleName")
    private String simpleName;

    @JsonProperty("kind")
    private String kind;

    @JsonProperty("annotations")
    private List<String> annotations = new ArrayList<>();

    @JsonProperty("fields")
    private List<FieldRecord> fields = new ArrayList<>();

    @JsonProperty("methods")
    private List<MethodRecord> methods = new ArrayList<>();

    @JsonProperty("invocations")
    private List<InvocationRecord> invocations = new ArrayList<>();

    public ClassRecord() {}

    public ClassRecord(String fqn, String simpleName, String kind,
                       List<String> annotations, List<FieldRecord> fields,
                       List<MethodRecord> methods, List<InvocationRecord> invocations) {
        this.fqn = fqn;
        this.simpleName = simpleName;
        this.kind = kind;
        this.annotations = annotations;
        this.fields = fields;
        this.methods = methods;
        this.invocations = invocations;
    }

    public String getFqn() { return fqn; }
    public void setFqn(String fqn) { this.fqn = fqn; }

    public String getSimpleName() { return simpleName; }
    public void setSimpleName(String simpleName) { this.simpleName = simpleName; }

    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }

    public List<String> getAnnotations() { return annotations; }
    public void setAnnotations(List<String> annotations) { this.annotations = annotations; }

    public List<FieldRecord> getFields() { return fields; }
    public void setFields(List<FieldRecord> fields) { this.fields = fields; }

    public List<MethodRecord> getMethods() { return methods; }
    public void setMethods(List<MethodRecord> methods) { this.methods = methods; }

    public List<InvocationRecord> getInvocations() { return invocations; }
    public void setInvocations(List<InvocationRecord> invocations) { this.invocations = invocations; }
}
