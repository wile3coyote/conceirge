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
import com.example.conceirge.ui.SetupScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme {
                var savedUrl by remember { mutableStateOf(UrlStore.getUrl(this)) }

                if (savedUrl == null) {
                    SetupScreen(onConnect = { url ->
                        UrlStore.saveUrl(this, url)
                        savedUrl = url
                    })
                } else {
                    val api = remember(savedUrl) { RetrofitInstance.create(savedUrl!!) }
                    val repo = remember(api) { ConciergeRepository(api) }
                    val viewModel = remember(repo) { HomeViewModel(repo) }
                    HomeScreen(
                        viewModel = viewModel,
                        onChangeServer = {
                            UrlStore.clearUrl(this)
                            savedUrl = null
                        }
                    )
                }
            }
        }
    }
}
