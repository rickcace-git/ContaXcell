package com.contaxcell.app.ui

/**
 * Stable, presentation-only contract between the Compose UI and the app layer.
 *
 * Monetary values are already formatted for display, while editable amounts are
 * plain decimal strings. This keeps locale, rounding and privacy decisions in
 * the ViewModel/domain layer and makes previews and UI tests straightforward.
 */
data class ContaXcellUiState(
    val auth: AuthUiState = AuthUiState.Loading,
    val destination: AppDestination = AppDestination.QuickAdd,
    val balance: String = "0,00 \u20ac",
    val amountsHidden: Boolean = false,
    val theme: ThemePreference = ThemePreference.System,
    val sync: SyncUiState = SyncUiState(),
    val quickAdd: QuickAddUiState = QuickAddUiState(),
    val movements: MovementsUiState = MovementsUiState(),
    val summary: SummaryUiState = SummaryUiState(),
    val budgets: BudgetsUiState = BudgetsUiState(),
    val investments: InvestmentsUiState = InvestmentsUiState(),
    val recurring: RecurringUiState = RecurringUiState(),
    val debts: DebtsUiState = DebtsUiState(),
    val settings: SettingsUiState = SettingsUiState(),
    val loading: Boolean = false,
    val message: UiMessage? = null,
)

sealed interface AuthUiState {
    data object Loading : AuthUiState
    data class Gate(
        val previousSessionAvailable: Boolean = false,
        val defaultUser: String = "",
        val defaultServer: String = "",
        val inviteRequired: Boolean = false,
        val busy: Boolean = false,
        val error: String? = null,
    ) : AuthUiState
    data class SignedIn(val user: String = "", val server: String = "") : AuthUiState
}

enum class AppDestination(val label: String) {
    QuickAdd("Apuntar"),
    Movements("Movimientos"),
    Summary("Resumen"),
    Budgets("Presupuesto"),
    Investments("Inversiones"),
    Recurring("Peri\u00f3dicos"),
    Debts("Deudas"),
    Settings("Ajustes"),
}

enum class ThemePreference { System, Light, Dark }
enum class MovementKind { Expense, Income, Investment }
enum class DebtDirection { OwedToMe, IOwe }
enum class SummaryMode { SingleYear, MultipleYears, SingleMonth }
enum class MessageKind { Success, Info, Warning, Error }
enum class SyncStatus { Synced, Pending, Offline, Error }

data class UiMessage(val text: String, val kind: MessageKind = MessageKind.Info)
data class SyncUiState(
    val status: SyncStatus = SyncStatus.Synced,
    val label: String = "Al d\u00eda",
)

data class SelectableOption(val id: String, val label: String)

data class QuickAddUiState(
    val categories: List<CategoryOption> = emptyList(),
    val assets: List<SelectableOption> = emptyList(),
    val today: String = "",
    val recent: List<MovementRowUi> = emptyList(),
    val monthMetrics: List<MetricUi> = emptyList(),
    val cadences: List<String> = listOf(
        "Semanal", "Quincenal", "Mensual", "Bimestral", "Trimestral", "Semestral", "Anual",
    ),
    val saving: Boolean = false,
)

data class CategoryOption(
    val id: String,
    val label: String,
    val kind: MovementKind,
)

data class MovementDraft(
    val amount: String,
    val description: String,
    val categoryId: String,
    val date: String,
    val assetId: String? = null,
    val recurringCadence: String? = null,
)

data class MovementRowUi(
    val id: String,
    val date: String,
    val description: String,
    val category: String,
    val categoryId: String = "",
    val kind: MovementKind,
    val amount: String,
    val rawAmount: String = "",
    val balance: String = "",
    val asset: String = "",
    val assetId: String? = null,
)

data class MovementsUiState(
    val rows: List<MovementRowUi> = emptyList(),
    val categories: List<SelectableOption> = emptyList(),
    val editCategories: List<CategoryOption> = emptyList(),
    val assets: List<SelectableOption> = emptyList(),
    val months: List<SelectableOption> = emptyList(),
    val query: String = "",
    val categoryId: String? = null,
    val monthId: String? = null,
    val countLabel: String = "0 movimientos",
    val totalsLabel: String = "",
    val canLoadMore: Boolean = false,
    val loading: Boolean = false,
)

data class MetricUi(
    val id: String,
    val label: String,
    val value: String,
    val supporting: String = "",
    val tone: MetricTone = MetricTone.Neutral,
)

enum class MetricTone { Neutral, Positive, Negative, Investment, Muted }

data class SummaryUiState(
    val year: Int = 0,
    val availableYears: List<Int> = emptyList(),
    val mode: SummaryMode = SummaryMode.SingleYear,
    val selectionId: String = "",
    val selectorOptions: List<SelectableOption> = emptyList(),
    val periodLabel: String = "",
    val trendTitle: String = "Mes a mes",
    val showTrend: Boolean = true,
    val metrics: List<MetricUi> = emptyList(),
    val months: List<MonthSummaryUi> = emptyList(),
    val expenses: List<CategoryShareUi> = emptyList(),
    val income: List<CategoryShareUi> = emptyList(),
    val empty: Boolean = false,
)

data class MonthSummaryUi(
    val label: String,
    val income: Double,
    val expenses: Double,
    val investment: Double,
    val incomeLabel: String = "",
    val expensesLabel: String = "",
    val savingsLabel: String = "",
    val investmentLabel: String = "",
    val endBalanceLabel: String = "",
)

data class CategoryShareUi(
    val name: String,
    val amount: String,
    val fraction: Float,
    val percent: String,
)

data class BudgetsUiState(
    val monthId: String = "",
    val monthLabel: String = "",
    val months: List<SelectableOption> = emptyList(),
    val rows: List<BudgetRowUi> = emptyList(),
    val metrics: List<MetricUi> = emptyList(),
    val investmentMetrics: List<MetricUi> = emptyList(),
    val investmentGoal: String = "",
)

data class BudgetRowUi(
    val categoryId: String,
    val category: String,
    val limit: String,
    val rawLimit: String = "",
    val spent: String,
    val available: String,
    val consumedLabel: String,
    val fraction: Float,
    val overBudget: Boolean = false,
)

data class InvestmentsUiState(
    val metrics: List<MetricUi> = emptyList(),
    val assets: List<AssetUi> = emptyList(),
    val categoryGroups: List<InvestmentGroupUi> = emptyList(),
    val history: List<PortfolioHistoryUi> = emptyList(),
    val cashback: List<CashbackUi> = emptyList(),
    val purchases: List<PurchaseUi> = emptyList(),
    val selectedAssetId: String? = null,
    val quoteSearch: QuoteSearchUiState = QuoteSearchUiState(),
    val quoteHistory: List<QuotePointUi> = emptyList(),
    val quoteAveragePaid: Double? = null,
    val quoteAveragePaidLabel: String = "",
    val quoteStatus: String = "",
)

data class AssetUi(
    val id: String,
    val name: String,
    val category: String,
    val initial: String,
    val fromBank: String,
    val free: String,
    val contributed: String,
    val marketValue: String,
    val generated: String,
    val returnLabel: String,
    val valuedAt: String,
    val rawInitial: String = "",
    val rawMarketValue: String = "",
    val quoteSymbol: String = "",
    val quoteStatus: String = "Sin cotizaci\u00f3n autom\u00e1tica",
    val latestQuoteDate: String = "",
    val automaticallyQuoted: Boolean = false,
)

data class InvestmentGroupUi(
    val name: String,
    val assets: Int,
    val contributed: String,
    val marketValue: String,
    val generated: String,
    val weight: String,
)

data class PortfolioHistoryUi(
    val id: String,
    val date: String,
    val contributedValue: Double,
    val marketValue: Double,
    val contributed: String,
    val market: String,
    val generated: String,
    val returnLabel: String,
)

data class CashbackUi(
    val id: String,
    val date: String,
    val asset: String,
    val concept: String,
    val amount: String,
)

data class PurchaseUi(
    val id: String,
    val date: String,
    val invested: String,
    val units: String,
    val paidPrice: String,
    val currentValue: String,
    val generated: String,
    val returnLabel: String,
    val quoteAtPurchase: String = "",
    val quoteToday: String = "",
    val quoteChangeLabel: String = "",
)

data class QuoteSearchUiState(
    val assetId: String? = null,
    val query: String = "",
    val searching: Boolean = false,
    val results: List<QuoteSearchResultUi> = emptyList(),
    val error: String? = null,
)

data class QuoteSearchResultUi(
    val symbol: String,
    val name: String,
    val exchange: String,
    val currency: String,
    val latestPrice: String = "",
)

data class QuotePointUi(
    val date: String,
    val value: Double,
    val valueLabel: String,
)

data class RecurringUiState(
    val metrics: List<MetricUi> = emptyList(),
    val rows: List<RecurringRowUi> = emptyList(),
    val categories: List<CategoryOption> = emptyList(),
    val assets: List<SelectableOption> = emptyList(),
    val cadences: List<String> = listOf(
        "Semanal", "Quincenal", "Mensual", "Bimestral", "Trimestral", "Semestral", "Anual",
    ),
)

data class RecurringRowUi(
    val id: String,
    val name: String,
    val category: String,
    val categoryId: String = "",
    val amount: String,
    val rawAmount: String = "",
    val cadence: String,
    val nextPayment: String,
    val startDate: String = "",
    val endDate: String = "",
    val assetId: String? = null,
    val enabled: Boolean,
    val finished: Boolean = false,
    val kind: MovementKind = MovementKind.Expense,
)

data class RecurringDraft(
    val name: String,
    val categoryId: String,
    val amount: String,
    val cadence: String,
    val startDate: String,
    val endDate: String,
    val assetId: String? = null,
)

data class DebtsUiState(
    val metrics: List<MetricUi> = emptyList(),
    val rows: List<DebtRowUi> = emptyList(),
    val people: List<DebtPersonUi> = emptyList(),
    val categories: List<CategoryOption> = emptyList(),
    val today: String = "",
)

data class DebtRowUi(
    val id: String,
    val person: String,
    val concept: String,
    val date: String,
    val total: String,
    val rawTotal: String = "",
    val pending: String,
    val rawPending: String = "",
    val note: String = "",
    val direction: DebtDirection,
    val settled: Boolean = false,
)

data class DebtPersonUi(
    val person: String,
    val openItems: Int,
    val balance: String,
    val tone: MetricTone,
)

data class DebtDraft(
    val direction: DebtDirection,
    val person: String,
    val concept: String,
    val amount: String,
    val date: String,
    val note: String,
)

data class DebtSettlementDraft(
    val amount: String,
    val date: String,
    val createMovement: Boolean,
    val categoryId: String? = null,
)

data class SettingsUiState(
    val initialBalance: String = "",
    val bankMetrics: List<MetricUi> = emptyList(),
    val categories: List<CategorySettingsUi> = emptyList(),
    val account: AccountUi = AccountUi(),
    val appVersion: String = "",
    val dataLocation: String = "Datos privados de la aplicaci\u00f3n",
)

data class CategorySettingsUi(
    val id: String,
    val name: String,
    val kind: MovementKind,
    val budget: String,
    val rawBudget: String = "",
    val uses: Int,
)

data class CategoryDraft(
    val name: String,
    val kind: MovementKind,
    val budget: String,
)

data class AssetDraft(
    val name: String,
    val category: String,
    val initial: String,
    val marketValue: String,
    val quoteSymbol: String = "",
)

data class AccountUi(
    val signedIn: Boolean = false,
    val user: String = "",
    val server: String = "",
    val syncDetail: String = "",
    val sessionExpired: Boolean = false,
)

sealed interface AppAction {
    data class Navigate(val destination: AppDestination) : AppAction
    data object ToggleAmounts : AppAction
    data class SignIn(val user: String, val password: String, val server: String) : AppAction
    data class Register(
        val user: String,
        val password: String,
        val server: String,
        val inviteCode: String,
    ) : AppAction
    data object ContinueOffline : AppAction
    data object DismissMessage : AppAction
    data object Retry : AppAction

    data class AddMovement(val draft: MovementDraft) : AppAction
    data class UpdateMovement(val id: String, val draft: MovementDraft) : AppAction
    data class DeleteMovement(val id: String) : AppAction
    data class SearchMovements(val query: String) : AppAction
    data class FilterMovements(val categoryId: String?, val monthId: String?) : AppAction
    data object LoadMoreMovements : AppAction

    data class SelectSummaryYear(val year: Int) : AppAction
    data class SelectSummaryMode(val mode: SummaryMode) : AppAction
    data class SelectSummaryPeriod(val selectionId: String) : AppAction
    data class SelectBudgetMonth(val monthId: String) : AppAction
    data class UpdateBudget(val categoryId: String, val amount: String) : AppAction
    data class UpdateInvestmentGoal(val amount: String) : AppAction

    data class SelectAsset(val id: String) : AppAction
    data class SaveAsset(val id: String?, val draft: AssetDraft) : AppAction
    data class DeleteAsset(val id: String) : AppAction
    data class AddPortfolioValue(val date: String, val amount: String) : AppAction
    data class DeletePortfolioValue(val id: String) : AppAction
    data class AddCashback(
        val date: String,
        val assetId: String?,
        val concept: String,
        val amount: String,
    ) : AppAction
    data class DeleteCashback(val id: String) : AppAction
    data object ImportTradeRepublic : AppAction
    data class SearchQuotes(val assetId: String, val query: String) : AppAction
    data class SelectQuote(val assetId: String, val symbol: String?) : AppAction
    data object RefreshQuotes : AppAction

    data class SaveRecurring(val id: String?, val draft: RecurringDraft) : AppAction
    data class ToggleRecurring(val id: String) : AppAction
    data class DeleteRecurring(val id: String) : AppAction

    data class SaveDebt(val id: String?, val draft: DebtDraft) : AppAction
    data class UpdateDebtNote(val id: String, val note: String) : AppAction
    data class SettleDebt(val id: String, val draft: DebtSettlementDraft) : AppAction
    data class DeleteDebt(val id: String) : AppAction

    data class UpdateInitialBalance(val amount: String) : AppAction
    data class SaveCategory(val id: String?, val draft: CategoryDraft) : AppAction
    data class MoveCategory(val id: String, val direction: Int) : AppAction
    data class DeleteCategory(val id: String) : AppAction
    data class SetTheme(val preference: ThemePreference) : AppAction
    data object ImportExcel : AppAction
    data object ExportExcel : AppAction
    data object SaveBackup : AppAction
    data object RestoreBackup : AppAction
    data class ChangePassword(val current: String, val new: String) : AppAction
    data object SignOut : AppAction
}
