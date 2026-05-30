package com.aigriculture.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import com.aigriculture.app.data.net.Net

class AIgricultureApp : Application(), ImageLoaderFactory {
    override fun onCreate() {
        super.onCreate()
        Net.init(this)
    }

    // Route Coil image loads through the authenticated OkHttp client so cookie-gated
    // /storage_img/* evidence photos load inside FLORA chat (and anywhere else).
    override fun newImageLoader(): ImageLoader =
        ImageLoader.Builder(this)
            .okHttpClient { Net.client }
            .crossfade(true)
            .build()
}
