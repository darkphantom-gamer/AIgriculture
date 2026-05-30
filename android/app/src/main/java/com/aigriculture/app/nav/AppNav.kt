package com.aigriculture.app.nav

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.ui.connect.ConnectScreen
import com.aigriculture.app.ui.login.LoginScreen
import com.aigriculture.app.ui.shell.AppShell

object Routes {
    const val CONNECT = "connect"
    const val LOGIN = "login"
    const val SHELL = "shell"
}

@Composable
fun AppNav() {
    val nav = rememberNavController()
    val start = if (Net.hasBaseUrl()) Routes.LOGIN else Routes.CONNECT

    NavHost(navController = nav, startDestination = start) {
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
