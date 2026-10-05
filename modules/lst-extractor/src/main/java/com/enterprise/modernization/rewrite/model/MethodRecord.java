package com.enterprise.modernization.rewrite.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

import java.util.ArrayList;
import java.util.List;

/**
 * Represents a single method declaration extracted from the LST,
 * including signature, metadata, control-flow branch count, explicit thrown exceptions,
 * and body source block for business logic methods.
 */
@JsonPropertyOrder({
    "name", "returnType", "parameterTypes", "annotations",
    "signature", "thrownExceptions", "branchCount", "bodySource"
})
public class MethodRecord {

    @JsonProperty("name")
    private String name;

    @JsonProperty("returnType")
    private String returnType = "void";

    @JsonProperty("parameterTypes")
    private List<String> parameterTypes = new ArrayList<>();

    @JsonProperty("annotations")
    private List<String> annotations = new ArrayList<>();

    @JsonProperty("signature")
    private String signature;

    @JsonProperty("thrownExceptions")
    private List<String> thrownExceptions = new ArrayList<>();

    @JsonProperty("branchCount")
    private int branchCount = 0;

    @JsonProperty("bodySource")
    @JsonInclude(JsonInclude.Include.NON_NULL)
    private String bodySource;

    public MethodRecord() {}

    public MethodRecord(String name, String returnType, List<String> parameterTypes,
                        List<String> annotations, String signature) {
        this(name, returnType, parameterTypes, annotations, signature, new ArrayList<>(), 0, null);
    }

    public MethodRecord(String name, String returnType, List<String> parameterTypes,
                        List<String> annotations, String signature,
                        List<String> thrownExceptions, int branchCount, String bodySource) {
        this.name = name;
        this.returnType = returnType;
        this.parameterTypes = parameterTypes;
        this.annotations = annotations;
        this.signature = signature;
        this.thrownExceptions = thrownExceptions != null ? thrownExceptions : new ArrayList<>();
        this.branchCount = branchCount;
        this.bodySource = bodySource;
    }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getReturnType() { return returnType; }
    public void setReturnType(String returnType) { this.returnType = returnType; }

    public List<String> getParameterTypes() { return parameterTypes; }
    public void setParameterTypes(List<String> parameterTypes) { this.parameterTypes = parameterTypes; }

    public List<String> getAnnotations() { return annotations; }
    public void setAnnotations(List<String> annotations) { this.annotations = annotations; }

    public String getSignature() { return signature; }
    public void setSignature(String signature) { this.signature = signature; }

    public List<String> getThrownExceptions() { return thrownExceptions; }
    public void setThrownExceptions(List<String> thrownExceptions) { this.thrownExceptions = thrownExceptions; }

    public int getBranchCount() { return branchCount; }
    public void setBranchCount(int branchCount) { this.branchCount = branchCount; }

    public String getBodySource() { return bodySource; }
    public void setBodySource(String bodySource) { this.bodySource = bodySource; }
}
