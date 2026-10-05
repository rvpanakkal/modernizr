package com.enterprise.modernization.rewrite.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

/**
 * Represents a dependency-injected field declaration.
 * Captures the injection annotation type (@EJB, @Inject, @Autowired, @PersistenceContext, @Resource).
 */
@JsonPropertyOrder({"name", "type", "typeFqn", "annotation"})
public class FieldRecord {

    @JsonProperty("name")
    private String name;

    @JsonProperty("type")
    private String type;

    @JsonProperty("typeFqn")
    @JsonInclude(JsonInclude.Include.NON_NULL)
    private String typeFqn;

    @JsonProperty("annotation")
    private String annotation;

    public FieldRecord() {}

    public FieldRecord(String name, String type, String typeFqn, String annotation) {
        this.name = name;
        this.type = type;
        this.typeFqn = typeFqn;
        this.annotation = annotation;
    }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public String getTypeFqn() { return typeFqn; }
    public void setTypeFqn(String typeFqn) { this.typeFqn = typeFqn; }

    public String getAnnotation() { return annotation; }
    public void setAnnotation(String annotation) { this.annotation = annotation; }
}
