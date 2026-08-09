package com.lqq.supportflow;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.importer.ClassFileImporter;
import org.junit.jupiter.api.Test;

class ArchitectureTest {

    private static final String DOMAIN = "..domain..";
    private static final String APPLICATION = "..application..";
    private static final String API = "..api..";
    private static final String INFRASTRUCTURE = "..infrastructure..";

    @Test
    void domainDoesNotDependOnOuterLayers() {
        noClasses().that().resideInAPackage(DOMAIN)
                .should().dependOnClassesThat().resideInAnyPackage(API, APPLICATION, INFRASTRUCTURE)
                .check(new ClassFileImporter().importPackages("com.lqq.supportflow"));
    }

    @Test
    void applicationDoesNotDependOnInfrastructure() {
        noClasses().that().resideInAPackage(APPLICATION)
                .should().dependOnClassesThat().resideInAPackage(INFRASTRUCTURE)
                .check(new ClassFileImporter().importPackages("com.lqq.supportflow"));
    }
}
