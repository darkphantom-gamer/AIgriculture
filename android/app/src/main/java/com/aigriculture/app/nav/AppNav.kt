package com.aigriculture.app.nav

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.ui.connect.ConnectScreen
import com.aigriculture.app.ui.login.LoginScreen
import com.aigriculture.app.ui.shell.AppShell
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg

object Routes {
    const val BOOT = "boot"
    const val CONNECT = "connect"
    const val LOGIN = "login"
    const val SHELL = "shell"
}

@Composable
fun AppNav() {
    val nav = rememberNavController()
    val start = when {
        !Net.hasBaseUrl() -> Routes.CONNECT
        Net.hasSessionCookie() -> Routes.BOOT
        else -> Routes.LOGIN
    }

    NavHost(navController = nav, startDestination = start) {
        composable(Routes.BOOT) {
            SessionBoot(
                onValid = {
                    nav.navigate(Routes.SHELL) {
                        popUpTo(Routes.BOOT) { inclusive = true }
                    }
                },
                onExpired = {
                    nav.navigate(Routes.LOGIN) {
                        popUpTo(Routes.BOOT) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.CONNECT) {
            ConnectScreen(
                onConnected = {
                    nav.navigate(Routes.LOGIN) {
                        popUpTo(Routes.CONNECT) { inclusive = true }
                    }
                }
            )
        }
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoggedIn = {
                    nav.navigate(Routes.SHELL) { popUpTo(0) }
                },
                onChangeServer = {
                    Net.forgetServer()
                    nav.navigate(Routes.CONNECT) { popUpTo(0) }
                }
            )
        }
        composable(Routes.SHELL) {
            AppShell(
                onLoggedOut = {
                    nav.navigate(Routes.LOGIN) { popUpTo(0) }
                }
            )
        }
    }
}

@Composable
private fun SessionBoot(onValid: () -> Unit, onExpired: () -> Unit) {
    LaunchedEffect(Unit) {
        when (val result = AigriRepository.me()) {
            is ApiResult.Ok -> onValid()
            is ApiResult.Err -> {
                val authRejected = result.code == 401 ||
                    result.code == 403 ||
                    result.message.contains("401") ||
                    result.message.contains("403")
                if (authRejected) {
                    Net.clearSession()
                    onExpired()
                } else {
                    onValid()
                }
            }
        }
    }
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(AigriBg),
        contentAlignment = Alignment.Center,
    ) {
        CircularProgressIndicator(color = AigriAccent)
    }
}
