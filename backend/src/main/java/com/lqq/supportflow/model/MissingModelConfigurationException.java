package com.lqq.supportflow.model;

public class MissingModelConfigurationException extends IllegalArgumentException {

    public MissingModelConfigurationException(String modelType) {
        super("default " + modelType + " model is not configured");
    }
}
