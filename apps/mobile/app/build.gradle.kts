import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    // AGP 9 provides built-in Kotlin compilation — no separate
    // kotlin-android plugin (and that is why the catalog never listed one).
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.google.devtools.ksp)
    // NOTE: the google-services plugin is intentionally NOT applied —
    // no main source imports Firebase and google-services.json is not
    // committed (secret hygiene). Re-add alias(libs.plugins.google.services)
    // here when Firebase is genuinely adopted.
}

android {
    namespace = "com.example"
    compileSdk = 36

    defaultConfig {
        // The applicationId must match the already-installed AI-Studio build
        // (com.aistudio.dash.vxzkmp) so the release APK upgrades it instead of
        // installing a second app. namespace (code/R) stays com.example.
        applicationId = "com.aistudio.dash.vxzkmp"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "1.0.0"

        // DASH_* fields are injected from the gitignored app/.env exactly as
        // the previous build pipeline did — secret values never enter the
        // repository, only the local APK.
        val envFile = rootProject.file("app/.env")
        val env = Properties()
        if (envFile.exists()) {
            envFile.inputStream().use { env.load(it) }
        }
        fun dashField(name: String, fallback: String = "") {
            val value = (env.getProperty(name) ?: fallback).replace("\\", "\\\\").replace("\"", "\\\"")
            buildConfigField("String", name, "\"$value\"")
        }
        dashField("DASH_SERVER_IP")
        dashField("DASH_SERVER_PORT", "8000")
        dashField("DASH_ACCESS_TOKEN")
        dashField("DASH_REFRESH_TOKEN")
    }

    // Production signing: drop a keystore.properties next to this file with
    // storeFile/storePassword/keyAlias/keyPassword pointing at my-upload-key.jks.
    // Without it, the release APK is signed with the debug key so it remains
    // installable for development.
    val keystorePropsFile = rootProject.file("keystore.properties")
    val keystoreProps = Properties()
    if (keystorePropsFile.exists()) {
        keystorePropsFile.inputStream().use { keystoreProps.load(it) }
    }

    signingConfigs {
        if (keystorePropsFile.exists()) {
            create("release") {
                storeFile = file(keystoreProps["storeFile"] as String)
                storePassword = keystoreProps["storePassword"] as String
                keyAlias = keystoreProps["keyAlias"] as String
                keyPassword = keystoreProps["keyPassword"] as String
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (keystorePropsFile.exists()) {
                signingConfig = signingConfigs.getByName("release")
            } else {
                signingConfig = signingConfigs.getByName("debug")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)

    // Compose (BOM-aligned)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.core)
    implementation(libs.androidx.compose.material.icons.extended)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

    implementation(libs.androidx.navigation.compose)

    // Room
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.coroutines.core)

    // Network
    implementation(libs.okhttp)
    implementation(libs.logging.interceptor)
    implementation(libs.retrofit)
    implementation(libs.converter.moshi)
    implementation(libs.moshi.kotlin)

    // Shimmer loading skeletons (ui/components/ShimmerSkeleton.kt)
    implementation("com.valentinilk.shimmer:compose-shimmer-android:1.3.1")

    // Encrypted local storage (data/security/SecurityManager.kt)
    implementation("androidx.security:security-crypto:1.1.0")

    // WebSocket client for the DASH backend (data/websocket/WebSocketManager.kt)
    implementation("org.java-websocket:Java-WebSocket:1.5.4")

    // Unit tests
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.core)
    testImplementation(libs.androidx.junit)

    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.runner)
}
