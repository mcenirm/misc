plugins {
    application
    id("com.gradleup.shadow") version "9.+"
    // id("com.github.ben-manes.versions") version "0.+"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("com.github.javaparser:javaparser-core:3.+")
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
    }
}

application {
    mainClass.set("FindJavaMains")
}
