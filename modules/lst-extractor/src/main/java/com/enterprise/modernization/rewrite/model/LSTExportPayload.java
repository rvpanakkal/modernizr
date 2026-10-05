package com.enterprise.modernization.rewrite.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

import java.util.ArrayList;
import java.util.List;

/**
 * Top-level JSON export schema for the OpenRewrite Lossless Semantic Tree extraction.
 * Schema version: 1.0.0
 * JSON field: "classes" (list of ClassRecord)
 */
@JsonPropertyOrder({"schemaVersion", "extractedAt", "sourceDirectory", "classes"})
public class LSTExportPayload {

    @JsonProperty("schemaVersion")
    private String schemaVersion = "1.0.0";

    @JsonProperty("extractedAt")
    private String extractedAt;

    @JsonProperty("sourceDirectory")
    private String sourceDirectory;

    @JsonProperty("classes")
    private List<ClassRecord> classes = new ArrayList<>();

    public LSTExportPayload() {}

    public LSTExportPayload(String extractedAt, String sourceDirectory, List<ClassRecord> classes) {
        this.extractedAt = extractedAt;
        this.sourceDirectory = sourceDirectory;
        this.classes = classes;
    }

    public String getSchemaVersion() { return schemaVersion; }
    public void setSchemaVersion(String schemaVersion) { this.schemaVersion = schemaVersion; }

    public String getExtractedAt() { return extractedAt; }
    public void setExtractedAt(String extractedAt) { this.extractedAt = extractedAt; }

    public String getSourceDirectory() { return sourceDirectory; }
    public void setSourceDirectory(String sourceDirectory) { this.sourceDirectory = sourceDirectory; }

    public List<ClassRecord> getClasses() { return classes; }
    public void setClasses(List<ClassRecord> classes) { this.classes = classes; }
}
