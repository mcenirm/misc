plugins {
    application
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("com.github.javaparser:javaparser-core:3.25.5")
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(8))
    }
}

application {
    mainClass.set("FindJavaMains")
}

tasks.register<Jar>("uberJar") {
    archiveClassifier.set("uber")
    from(sourceSets.main.get().output)
    dependsOn(configurations.runtimeClasspath)
    from({
        configurations.runtimeClasspath.get().filter { it.name.endsWith("jar") }.map { zipTree(it) }
    })
}
