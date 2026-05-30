package com.aigriculture.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.aigriculture.app.nav.AppNav
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigricultureTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AigricultureTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = AigriBg) {
                    AppNav()
                }
            }
        }
    }
}
