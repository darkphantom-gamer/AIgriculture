package com.aigriculture.app

import android.app.Application
import com.aigriculture.app.data.net.Net

class AIgricultureApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Net.init(this)
    }
}
