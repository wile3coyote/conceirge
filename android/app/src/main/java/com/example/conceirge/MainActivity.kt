package com.example.conceirge

import android.Manifest
import android.app.Application
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.conceirge.data.ConciergeRepository
import com.example.conceirge.data.UrlStore
import com.example.conceirge.data.models.AppSettingsUpdate
import com.example.conceirge.data.network.RetrofitInstance
import com.example.conceirge.ui.HomeScreen
import com.example.conceirge.ui.HomeViewModel
import com.example.conceirge.ui.LibraryDetailScreen
import com.example.conceirge.ui.SettingsScreen
import com.example.conceirge.ui.SettingsViewModel
import com.example.conceirge.ui.SetupScreen
import com.example.conceirge.ui.StatusScreen
import com.example.conceirge.ui.StatusViewModel
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    // ---------------------------------------------------------------------------
    // Resume events — HomeViewModel (wired in a separate task) subscribes to this.
    // ---------------------------------------------------------------------------
    private val _resumeEvents = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val resumeEvents = _resumeEvents.asSharedFlow()

    // ---------------------------------------------------------------------------
    // Deep-link channel — set in onNewIntent / intent read in onCreate, collected
    // inside the Composable via LaunchedEffect so navController is in scope.
    // ---------------------------------------------------------------------------
    private val _pendingNavigation = MutableStateFlow<String?>(null)
    val pendingNavigation = _pendingNavigation.asStateFlow()

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) {}

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        enableEdgeToEdge()

        // Register lifecycle observer to expose ON_RESUME as a SharedFlow.
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onResume(owner: LifecycleOwner) {
                _resumeEvents.tryEmit(Unit)
            }
        })

        // Seed the deep-link channel with the cold-start intent (if any).
        intent.getStringExtra("navigate_to")?.let { destination ->
            _pendingNavigation.value = destination
        }

        UrlStore.getUrl(this)?.let { url ->
            FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                lifecycleScope.launch {
                    runCatching {
                        RetrofitInstance.create(url).updateSettings(AppSettingsUpdate(fcm_token = token))
                    }
                }
            }
        }

        setContent {
            MaterialTheme {
                var savedUrl by remember { mutableStateOf(UrlStore.getUrl(this)) }

                if (savedUrl == null) {
                    // No server configured yet — show setup outside of NavHost so the
                    // nav graph is only reachable once a URL exists.
                    SetupScreen(onConnect = { url ->
                        UrlStore.saveUrl(this, url)
                        savedUrl = url
                    })
                } else {
                    val api = remember(savedUrl) { RetrofitInstance.create(savedUrl!!) }
                    val repo = remember(api) { ConciergeRepository(api) }

                    val navController = rememberNavController()

                    // Collect deep-link destinations (both cold-start and onNewIntent).
                    val pendingNav by pendingNavigation.collectAsState()
                    LaunchedEffect(pendingNav) {
                        pendingNav?.let { destination ->
                            navController.navigate(destination)
                            _pendingNavigation.value = null
                        }
                    }

                    NavHost(navController = navController, startDestination = "home") {

                        composable("home") {
                            val application = LocalContext.current.applicationContext as Application
                            val vm: HomeViewModel = viewModel(
                                factory = HomeViewModel.Factory(application, repo)
                            )
                            // Trigger an immediate fetch + stale-error recovery whenever
                            // the activity comes back to the foreground.
                            LaunchedEffect(Unit) {
                                resumeEvents.collect { vm.onResumed() }
                            }
                            HomeScreen(
                                viewModel = vm,
                                onOpenDetail = { id -> navController.navigate("library/$id") },
                                onChangeServer = {
                                    UrlStore.clearUrl(this@MainActivity)
                                    savedUrl = null
                                },
                                onOpenSettings = { navController.navigate("settings") },
                                onOpenStatus = { navController.navigate("status") }
                            )
                        }

                        composable(
                            route = "library/{id}",
                            arguments = listOf(navArgument("id") { type = NavType.IntType })
                        ) { backStackEntry ->
                            val id = backStackEntry.arguments?.getInt("id")
                                ?: return@composable
                            LibraryDetailScreen(
                                libraryItemId = id,
                                onBack = { navController.popBackStack() }
                            )
                        }

                        composable("settings") {
                            val vm = remember(repo) { SettingsViewModel(repo) }
                            SettingsScreen(
                                viewModel = vm,
                                onBack = { navController.popBackStack() },
                                onOpenStatus = { navController.navigate("status") }
                            )
                        }

                        composable("status") {
                            val vm = remember(repo) { StatusViewModel(repo) }
                            StatusScreen(
                                viewModel = vm,
                                backendUrl = savedUrl!!,
                                onBack = { navController.popBackStack() }
                            )
                        }

                        composable("setup") {
                            SetupScreen(onConnect = { url ->
                                UrlStore.saveUrl(this@MainActivity, url)
                                savedUrl = url
                                navController.navigate("home") {
                                    popUpTo(0) { inclusive = true }
                                }
                            })
                        }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // Framework hook — keeps the Activity's intent current for any future reads.
        setIntent(intent)
        // Push the destination into the channel; the LaunchedEffect inside setContent
        // will observe the new value and call navController.navigate().
        intent.getStringExtra("navigate_to")?.let { destination ->
            _pendingNavigation.value = destination
        }
    }
}
