package com.enterprise.modernization.rewrite.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

import java.util.ArrayList;
import java.util.List;

/**
 * Represents a single method invocation extracted from the LST call graph.
 * Maps caller → target including fully qualified class names.
 */
@JsonPropertyOrder({"callerClassFqn", "callerMethodName", "targetClassFqn", "targetMethodName", "returnType", "argumentTypes"})
public class InvocationRecord {

    @JsonProperty("callerClassFqn")
    private String callerClassFqn;

    @JsonProperty("callerMethodName")
    private String callerMethodName;

    @JsonProperty("targetClassFqn")
    private String targetClassFqn;

    @JsonProperty("targetMethodName")
    private String targetMethodName;

    @JsonProperty("returnType")
    private String returnType = "void";

    @JsonProperty("argumentTypes")
    private List<String> argumentTypes = new ArrayList<>();

    public InvocationRecord() {}

    public InvocationRecord(String callerClassFqn, String callerMethodName,
                            String targetClassFqn, String targetMethodName,
                            String returnType, List<String> argumentTypes) {
        this.callerClassFqn = callerClassFqn;
        this.callerMethodName = callerMethodName;
        this.targetClassFqn = targetClassFqn;
        this.targetMethodName = targetMethodName;
        this.returnType = returnType;
        this.argumentTypes = argumentTypes;
    }

    public String getCallerClassFqn() { return callerClassFqn; }
    public void setCallerClassFqn(String callerClassFqn) { this.callerClassFqn = callerClassFqn; }

    public String getCallerMethodName() { return callerMethodName; }
    public void setCallerMethodName(String callerMethodName) { this.callerMethodName = callerMethodName; }

    public String getTargetClassFqn() { return targetClassFqn; }
    public void setTargetClassFqn(String targetClassFqn) { this.targetClassFqn = targetClassFqn; }

    public String getTargetMethodName() { return targetMethodName; }
    public void setTargetMethodName(String targetMethodName) { this.targetMethodName = targetMethodName; }

    public String getReturnType() { return returnType; }
    public void setReturnType(String returnType) { this.returnType = returnType; }

    public List<String> getArgumentTypes() { return argumentTypes; }
    public void setArgumentTypes(List<String> argumentTypes) { this.argumentTypes = argumentTypes; }
}
