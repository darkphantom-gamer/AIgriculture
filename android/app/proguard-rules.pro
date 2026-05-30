# Keep kotlinx-serialization metadata for serializable models.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class **$$serializer { *; }
-keepclasseswithmembers class com.aigriculture.app.data.net.** {
    *** Companion;
}
-keepclassmembers class com.aigriculture.app.data.net.** {
    kotlinx.serialization.KSerializer serializer(...);
}
# OkHttp / Okio
-dontwarn okhttp3.**
-dontwarn okio.**
