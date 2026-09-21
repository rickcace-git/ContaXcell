package com.contaxcell.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.Assessment
import androidx.compose.material.icons.outlined.Autorenew
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Handshake
import androidx.compose.material.icons.outlined.Insights
import androidx.compose.material.icons.outlined.Menu
import androidx.compose.material.icons.outlined.Payments
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.screens.AuthScreen
import com.contaxcell.app.ui.screens.BudgetsScreen
import com.contaxcell.app.ui.screens.DebtsScreen
import com.contaxcell.app.ui.screens.InvestmentsScreen
import com.contaxcell.app.ui.screens.MovementsScreen
import com.contaxcell.app.ui.screens.QuickAddScreen
import com.contaxcell.app.ui.screens.RecurringScreen
import com.contaxcell.app.ui.screens.SettingsScreen
import com.contaxcell.app.ui.screens.SummaryScreen
import com.contaxcell.app.ui.theme.ContaXcellTheme
import kotlinx.coroutines.launch

/** Root Compose entry used by MainActivity. */
@Composable
fun ContaXcellApp(
    state: ContaXcellUiState,
    onAction: (AppAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    ContaXcellTheme(state.theme) {
        Surface(modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            when (val auth = state.auth) {
                AuthUiState.Loading -> AppLoading()
                is AuthUiState.Gate -> AuthScreen(auth, onAction)
                is AuthUiState.SignedIn -> AppShell(state, onAction)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppShell(state: ContaXcellUiState, onAction: (AppAction) -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val wide = maxWidth >= 840.dp
        if (wide) {
            Scaffold(topBar = { AppTopBar(state, menu = null, onAction) }) { padding ->
                Row(Modifier.fillMaxSize().padding(padding)) {
                    AppNavigationRail(state.destination) { onAction(AppAction.Navigate(it)) }
                    Box(Modifier.weight(1f).fillMaxHeight()) {
                        DestinationContent(state, onAction)
                        LoadingOverlay(state.loading)
                    }
                }
            }
        } else {
            val drawerState = rememberDrawerState(DrawerValue.Closed)
            val scope = rememberCoroutineScope()
            ModalNavigationDrawer(
                drawerState = drawerState,
                drawerContent = {
                    ModalDrawerSheet(modifier = Modifier.width(304.dp)) {
                        DrawerHeader()
                        HorizontalDivider()
                        AppDestination.entries.forEach { destination ->
                            NavigationDrawerItem(
                                label = { Text(destination.label) },
                                selected = state.destination == destination,
                                onClick = {
                                    onAction(AppAction.Navigate(destination))
                                    scope.launch { drawerState.close() }
                                },
                                icon = { Icon(destination.icon(), contentDescription = null) },
                                modifier = Modifier.padding(horizontal = 12.dp),
                            )
                        }
                    }
                },
            ) {
                Scaffold(
                    topBar = {
                        AppTopBar(state, menu = { scope.launch { drawerState.open() } }, onAction)
                    },
                ) { padding ->
                    Box(Modifier.fillMaxSize().padding(padding)) {
                        DestinationContent(state, onAction)
                        LoadingOverlay(state.loading)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppTopBar(
    state: ContaXcellUiState,
    menu: (() -> Unit)?,
    onAction: (AppAction) -> Unit,
) {
    CenterAlignedTopAppBar(
        title = {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    if (state.amountsHidden) "Importes ocultos" else state.balance,
                    style = MaterialTheme.typography.titleLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(6.dp).background(syncColor(state.sync.status), CircleShape)
                            .semantics { contentDescription = state.sync.label },
                    )
                    Spacer(Modifier.width(5.dp))
                    Text(state.sync.label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        },
        navigationIcon = {
            if (menu != null) {
                IconButton(onClick = menu) { Icon(Icons.Outlined.Menu, contentDescription = "Abrir navegaci\u00f3n") }
            } else {
                Icon(Icons.Outlined.AccountBalanceWallet, contentDescription = null, modifier = Modifier.padding(start = 18.dp))
            }
        },
        actions = {
            IconButton(onClick = { onAction(AppAction.ToggleAmounts) }) {
                Icon(
                    if (state.amountsHidden) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                    contentDescription = if (state.amountsHidden) "Mostrar importes" else "Ocultar importes",
                )
            }
        },
        colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = MaterialTheme.colorScheme.surface),
    )
}

@Composable
private fun AppNavigationRail(selected: AppDestination, onSelected: (AppDestination) -> Unit) {
    NavigationRail(containerColor = MaterialTheme.colorScheme.surface) {
        Spacer(Modifier.padding(top = 8.dp))
        AppDestination.entries.forEach { destination ->
            NavigationRailItem(
                selected = selected == destination,
                onClick = { onSelected(destination) },
                icon = { Icon(destination.icon(), contentDescription = null) },
                label = { Text(destination.shortLabel()) },
            )
        }
    }
}

@Composable
private fun DrawerHeader() {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier.size(40.dp).background(MaterialTheme.colorScheme.primaryContainer, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.AccountBalanceWallet, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimaryContainer)
        }
        Column {
            Text("ContaXcell", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Contabilidad personal", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun DestinationContent(state: ContaXcellUiState, onAction: (AppAction) -> Unit) {
    Column(Modifier.fillMaxSize()) {
        state.message?.let { message ->
            com.contaxcell.app.ui.components.MessageBanner(
                message,
                { onAction(AppAction.DismissMessage) },
                Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }
        Box(Modifier.weight(1f)) {
            when (state.destination) {
                AppDestination.QuickAdd -> QuickAddScreen(state.quickAdd, onAction)
                AppDestination.Movements -> MovementsScreen(state.movements, onAction)
                AppDestination.Summary -> SummaryScreen(state.summary, onAction)
                AppDestination.Budgets -> BudgetsScreen(state.budgets, onAction)
                AppDestination.Investments -> InvestmentsScreen(state.investments, onAction)
                AppDestination.Recurring -> RecurringScreen(state.recurring, onAction)
                AppDestination.Debts -> DebtsScreen(state.debts, onAction)
                AppDestination.Settings -> SettingsScreen(state.settings, state.theme, state.amountsHidden, onAction)
            }
        }
    }
}

@Composable
private fun LoadingOverlay(loading: Boolean) {
    if (!loading) return
    Box(
        Modifier.fillMaxSize().background(MaterialTheme.colorScheme.scrim.copy(alpha = .18f)),
        contentAlignment = Alignment.Center,
    ) {
        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surface, shadowElevation = 4.dp) {
            CircularProgressIndicator(Modifier.padding(14.dp).size(24.dp), strokeWidth = 2.dp)
        }
    }
}

@Composable
private fun AppLoading() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(Icons.Outlined.AccountBalanceWallet, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(42.dp))
            Text("ContaXcell", style = MaterialTheme.typography.headlineMedium)
            CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
        }
    }
}

private fun AppDestination.icon(): ImageVector = when (this) {
    AppDestination.QuickAdd -> Icons.Outlined.Home
    AppDestination.Movements -> Icons.AutoMirrored.Outlined.ReceiptLong
    AppDestination.Summary -> Icons.Outlined.Assessment
    AppDestination.Budgets -> Icons.Outlined.Payments
    AppDestination.Investments -> Icons.Outlined.Insights
    AppDestination.Recurring -> Icons.Outlined.Autorenew
    AppDestination.Debts -> Icons.Outlined.Handshake
    AppDestination.Settings -> Icons.Outlined.Settings
}

private fun AppDestination.shortLabel() = when (this) {
    AppDestination.Budgets -> "Presup."
    AppDestination.Investments -> "Inversi\u00f3n"
    AppDestination.Recurring -> "Peri\u00f3dicos"
    AppDestination.Debts -> "Deudas"
    else -> label
}

@Composable
private fun syncColor(status: SyncStatus) = when (status) {
    SyncStatus.Synced -> MaterialTheme.colorScheme.primary
    SyncStatus.Pending -> com.contaxcell.app.ui.theme.Warning
    SyncStatus.Offline -> MaterialTheme.colorScheme.onSurfaceVariant
    SyncStatus.Error -> MaterialTheme.colorScheme.error
}
