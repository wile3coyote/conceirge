package com.example.conceirge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.UrlStore
import com.example.conceirge.data.network.RetrofitInstance
import com.example.conceirge.ui.HomeScreen
import com.example.conceirge.ui.HomeViewModel
import com.example.conceirge.ui.SettingsScreen
import com.example.conceirge.ui.SettingsViewModel
import com.example.conceirge.ui.SetupScreen
import com.example.conceirge.ui.StatusScreen
import com.example.conceirge.ui.StatusViewModel

private enum class Screen { Home, Settings, Status }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme {
                var savedUrl by remember { mutableStateOf(UrlStore.getUrl(this)) }
                var screen by remember { mutableStateOf(Screen.Home) }

                if (savedUrl == null) {
                    SetupScreen(onConnect = { url ->
                        UrlStore.saveUrl(this, url)
                        savedUrl = url
                    })
                } else {
                    val api = remember(savedUrl) { RetrofitInstance.create(savedUrl!!) }
                    val repo = remember(api) { ConciergeRepository(api) }

                    when (screen) {
                        Screen.Home -> {
                            val vm = remember(repo) { HomeViewModel(repo) }
                            HomeScreen(
                                viewModel = vm,
                                onChangeServer = {
                                    UrlStore.clearUrl(this)
                                    savedUrl = null
                                    screen = Screen.Home
                                },
                                onOpenSettings = { screen = Screen.Settings }
                            )
                        }
                        Screen.Settings -> {
                            val vm = remember(repo) { SettingsViewModel(repo) }
                            SettingsScreen(
                                viewModel = vm,
                                onBack = { screen = Screen.Home },
                                onOpenStatus = { screen = Screen.Status }
                            )
                        }
                        Screen.Status -> {
                            val vm = remember(repo) { StatusViewModel(repo) }
                            StatusScreen(
                                viewModel = vm,
                                backendUrl = savedUrl!!,
                                onBack = { screen = Screen.Settings }
                            )
                        }
                    }
                }
            }
        }
    }
}
