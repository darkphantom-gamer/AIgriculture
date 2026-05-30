package com.aigriculture.app.data.net

import kotlinx.serialization.json.JsonElement
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ApiService {

    // Public page — used to validate that an address is an AIgriculture server.
    @GET("login")
    suspend fun probeLogin(): Response<ResponseBody>

    @FormUrlEncoded
    @POST("auth/login")
    suspend fun login(
        @Field("username") username: String,
        @Field("password") password: String,
    ): Response<LoginResp>

    @POST("auth/logout")
    suspend fun logout(): Response<ResponseBody>

    @GET("api/me")
    suspend fun me(): MeResp

    @GET("api/flora/status")
    suspend fun floraStatus(): FloraStatusResp

    // Returns a JSON array of tasks, or {"error": ...}; handled loosely.
    @GET("api/flora/schedule")
    suspend fun floraSchedule(): Response<JsonElement>

    @GET("api/plants")
    suspend fun plants(): PlantsResp

    @GET("api/state")
    suspend fun state(): StateMsg

    @POST("api/pump/{plant}/{action}")
    suspend fun pump(
        @Path("plant") plant: String,
        @Path("action") action: String,
    ): Response<PumpResp>

    @POST("api/auto_irrigation")
    suspend fun autoIrrigation(@Body body: AutoIrrReq): Response<AutoIrrResp>

    // HTTP fallback for FLORA chat when a reverse proxy blocks WebSocket upgrades.
    @POST("api/flora/chat")
    suspend fun floraChat(@Body body: FloraChatReq): Response<FloraChatResp>

    @POST("set_presence")
    suspend fun setPresence(@Body body: PresenceReq): Response<PresenceResp>

    @POST("api/buzzer")
    suspend fun buzzerMute(@Body body: BuzzerReq): Response<SimpleOk>

    @POST("api/buzzer/test")
    suspend fun buzzerTest(): Response<SimpleOk>

    @POST("api/camera/{camera}/{action}")
    suspend fun camera(
        @Path("camera") camera: String,
        @Path("action") action: String,
    ): Response<CameraResp>

    @GET("alerts")
    suspend fun alerts(): AlertsResp

    @GET("api/farm_monitor/status")
    suspend fun farmStatus(): FarmStatus

    @POST("api/farm_monitor/scan_now")
    suspend fun scanNow(): Response<SimpleOk>

    @GET("api/analytics")
    suspend fun analytics(): AnalyticsResp

    // Nested tree: { year: { month: { day: [StorageEvent] } } }.
    @GET("api/storage")
    suspend fun storage(): Map<String, Map<String, Map<String, List<StorageEvent>>>>

    @GET("api/sensors/scan")
    suspend fun sensorsScan(): Response<SensorScanResp>

    @POST("api/sensors/add")
    suspend fun sensorsAdd(@Body body: SensorAddReq): Response<SensorAddResp>

    @GET("api/notification_email")
    suspend fun notifEmailGet(): NotifEmailResp

    @POST("api/notification_email")
    suspend fun notifEmailSet(@Body body: NotifEmailReq): Response<NotifEmailResp>
}
