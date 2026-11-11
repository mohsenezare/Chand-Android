pluginManagement {
    repositories {
        System.getenv("LOCAL_MAVEN_PROXY")?.let { proxy ->
            maven { url = uri("$proxy/google"); isAllowInsecureProtocol = true }
            maven { url = uri("$proxy/central"); isAllowInsecureProtocol = true }
            maven { url = uri("$proxy/plugins"); isAllowInsecureProtocol = true }
        }
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        System.getenv("LOCAL_MAVEN_PROXY")?.let { proxy ->
            maven { url = uri("$proxy/google"); isAllowInsecureProtocol = true }
            maven { url = uri("$proxy/central"); isAllowInsecureProtocol = true }
        }
        google()
        mavenCentral()
    }
}

rootProject.name = "ChandAndroidPersonal"
include(":app")
