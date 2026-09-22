package com.contaxcell.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.contaxcell.app.data.local.JsonLibroStore
import com.contaxcell.app.data.local.LibroStore
import com.contaxcell.app.data.excel.ExcelBookService
import com.contaxcell.app.data.excel.TradeRepublicImporter
import com.contaxcell.app.data.excel.TradeRepublicOptions
import com.contaxcell.app.data.remote.AuthRepository
import com.contaxcell.app.data.remote.AccountChangeHandler
import com.contaxcell.app.data.remote.AuthenticationException
import com.contaxcell.app.data.remote.OkHttpContaXcellApi
import com.contaxcell.app.data.remote.MarketQuoteRepository
import com.contaxcell.app.data.remote.QuoteSearchResult
import com.contaxcell.app.data.sync.DomainMarketQuoteBookPort
import com.contaxcell.app.data.sync.MarketQuoteSync
import com.contaxcell.app.data.sync.QuoteRefreshResult
import com.contaxcell.app.data.sync.SharedPreferencesSessionStore
import com.contaxcell.app.data.sync.SyncBookStore
import com.contaxcell.app.data.sync.SyncEngine
import com.contaxcell.app.data.sync.SyncEvent
import com.contaxcell.app.data.sync.SyncEventSink
import com.contaxcell.app.data.sync.SyncResult
import com.contaxcell.app.data.sync.SyncScheduler
import com.contaxcell.app.domain.Activo
import com.contaxcell.app.domain.Ajustes
import com.contaxcell.app.domain.AportacionGratis
import com.contaxcell.app.domain.Calculos
import com.contaxcell.app.domain.Categoria
import com.contaxcell.app.domain.ContaXcellValues
import com.contaxcell.app.domain.Deuda
import com.contaxcell.app.domain.IsoDates
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import com.contaxcell.app.domain.Periodico
import com.contaxcell.app.domain.SpanishFormat
import com.contaxcell.app.domain.Valoracion
import com.contaxcell.app.domain.newId
import com.contaxcell.app.ui.AccountUi
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.AppDestination
import com.contaxcell.app.ui.AssetUi
import com.contaxcell.app.ui.AuthUiState
import com.contaxcell.app.ui.BudgetRowUi
import com.contaxcell.app.ui.BudgetsUiState
import com.contaxcell.app.ui.CashbackUi
import com.contaxcell.app.ui.CategoryOption
import com.contaxcell.app.ui.CategorySettingsUi
import com.contaxcell.app.ui.CategoryShareUi
import com.contaxcell.app.ui.ContaXcellUiState
import com.contaxcell.app.ui.DebtDirection
import com.contaxcell.app.ui.DebtPersonUi
import com.contaxcell.app.ui.DebtRowUi
import com.contaxcell.app.ui.DebtsUiState
import com.contaxcell.app.ui.InvestmentGroupUi
import com.contaxcell.app.ui.InvestmentsUiState
import com.contaxcell.app.ui.MessageKind
import com.contaxcell.app.ui.MetricTone
import com.contaxcell.app.ui.MetricUi
import com.contaxcell.app.ui.MonthSummaryUi
import com.contaxcell.app.ui.MovementKind
import com.contaxcell.app.ui.MovementRowUi
import com.contaxcell.app.ui.MovementsUiState
import com.contaxcell.app.ui.PortfolioHistoryUi
import com.contaxcell.app.ui.PurchaseUi
import com.contaxcell.app.ui.QuotePointUi
import com.contaxcell.app.ui.QuoteSearchResultUi
import com.contaxcell.app.ui.QuoteSearchUiState
import com.contaxcell.app.ui.QuickAddUiState
import com.contaxcell.app.ui.RecurringRowUi
import com.contaxcell.app.ui.RecurringUiState
import com.contaxcell.app.ui.SelectableOption
import com.contaxcell.app.ui.SettingsUiState
import com.contaxcell.app.ui.SummaryUiState
import com.contaxcell.app.ui.SummaryMode
import com.contaxcell.app.ui.SyncStatus
import com.contaxcell.app.ui.SyncUiState
import com.contaxcell.app.ui.ThemePreference
import com.contaxcell.app.ui.UiMessage
import java.io.InputStream
import java.io.OutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

sealed interface AppEffect {
    data object ChooseExcelImport : AppEffect
    data class ChooseExcelExport(val suggestedName: String) : AppEffect
    data object ChooseTradeRepublicPdf : AppEffect
}

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val store: LibroStore = JsonLibroStore(application.filesDir)
    private val sessions = SharedPreferencesSessionStore(application)
    private val api = OkHttpContaXcellApi()
    private val authRepository = AuthRepository(
        api,
        sessions,
        AccountChangeHandler { _, _ ->
            withContext(Dispatchers.IO) {
                store.backup("cambio-de-usuario")
                store.replace(Libro.empty(), "antes-de-cambiar-usuario")
            }
            book = Libro.empty()
        },
    )
    private val mutationMutex = Mutex()

    private var book = Libro.empty()
    private var auth: AuthUiState = AuthUiState.Loading
    private var destination = AppDestination.QuickAdd
    private var selectedYear = IsoDates.today().take(4).toInt()
    private var selectedMonth = IsoDates.monthOf(IsoDates.today())
    private var summaryMode = SummaryMode.SingleYear
    private var summarySelection = selectedYear.toString()
    private var movementQuery = ""
    private var movementCategory: String? = null
    private var movementMonth: String? = null
    private var movementLimit = 80
    private var selectedAsset: String? = null
    private var quoteSearchAsset: String? = null
    private var quoteSearchQuery = ""
    private var quoteSearching = false
    private var quoteSearchError: String? = null
    private var quoteSearchResults: List<QuoteSearchResult> = emptyList()
    private var syncUi = SyncUiState(SyncStatus.Synced, "Solo en este dispositivo")
    private var message: UiMessage? = null
    private var busy = true

    private val _state = MutableStateFlow(ContaXcellUiState())
    val state: StateFlow<ContaXcellUiState> = _state.asStateFlow()
    private val _effects = MutableSharedFlow<AppEffect>(extraBufferCapacity = 4)
    val effects: SharedFlow<AppEffect> = _effects.asSharedFlow()

    private val syncEngine = createSyncEngine()
    private val quoteRepository = MarketQuoteRepository(api, sessions)
    private val quoteSync = MarketQuoteSync(
        quoteRepository,
        DomainMarketQuoteBookPort(
            readBook = { book },
            writeBook = { next ->
                val normalized = next.normalized()
                withContext(Dispatchers.IO) { store.save(normalized) }
                book = normalized
            },
        ),
    )

    init {
        SyncScheduler.schedulePeriodic(getApplication())
        viewModelScope.launch { loadInitialState() }
    }

    fun dispatch(action: AppAction) {
        when (action) {
            is AppAction.Navigate -> { destination = action.destination; refresh() }
            AppAction.ToggleAmounts -> mutate("Preferencia de privacidad guardada") {
                it.copy(ajustes = it.ajustes.copy(ocultarImportes = !it.ajustes.ocultarImportes))
            }
            is AppAction.SignIn -> authenticate(false, action.user, action.password, action.server, "")
            is AppAction.Register -> authenticate(true, action.user, action.password, action.server, action.inviteCode)
            AppAction.ContinueOffline -> {
                auth = AuthUiState.SignedIn()
                syncUi = SyncUiState(SyncStatus.Offline, "Solo en este dispositivo")
                refresh()
            }
            AppAction.DismissMessage -> { message = null; refresh() }
            AppAction.Retry -> syncNow()
            is AppAction.AddMovement -> {
                val amount = requiredAmount(action.draft.amount) ?: return
                if (!IsoDates.isValid(action.draft.date)) return showError("La fecha no es válida.")
                val category = action.draft.categoryId.takeIf { id -> book.categoria(id) != null }
                    ?: return showError("Elige una categoría.")
                mutate("Movimiento guardado", MessageKind.Success) {
                    val movement = Movimiento(
                        fecha = action.draft.date,
                        descripcion = action.draft.description,
                        categoria = category,
                        importe = amount,
                        activo = action.draft.assetId.orEmpty(),
                    )
                    val cadence = action.draft.recurringCadence
                    if (cadence != null && cadence in ContaXcellValues.PERIODOS) {
                        val created = Calculos.periodicoDe(movement, cadence, IsoDates.today())
                        it.copy(
                            movimientos = it.movimientos + created.movimiento,
                            periodicos = it.periodicos + created.periodico,
                        )
                    } else it.copy(movimientos = it.movimientos + movement)
                }
            }
            is AppAction.UpdateMovement -> {
                val amount = requiredAmount(action.draft.amount) ?: return
                if (!IsoDates.isValid(action.draft.date)) return showError("La fecha no es válida.")
                mutate("Movimiento actualizado", MessageKind.Success) { current ->
                    current.copy(movimientos = current.movimientos.map { movement ->
                        if (movement.id != action.id) movement else movement.copy(
                            fecha = action.draft.date,
                            descripcion = action.draft.description.trim(),
                            categoria = action.draft.categoryId,
                            importe = amount,
                            activo = action.draft.assetId.orEmpty(),
                        )
                    })
                }
            }
            is AppAction.DeleteMovement -> mutate("Movimiento borrado") { current ->
                current.copy(movimientos = current.movimientos.filterNot { it.id == action.id })
            }
            is AppAction.SearchMovements -> { movementQuery = action.query; movementLimit = 80; refresh() }
            is AppAction.FilterMovements -> {
                movementCategory = action.categoryId
                movementMonth = action.monthId
                movementLimit = 80
                refresh()
            }
            AppAction.LoadMoreMovements -> { movementLimit += 80; refresh() }
            is AppAction.SelectSummaryYear -> {
                summaryMode = SummaryMode.SingleYear
                selectedYear = action.year
                summarySelection = action.year.toString()
                refresh()
            }
            is AppAction.SelectSummaryMode -> {
                summaryMode = action.mode
                summarySelection = when (action.mode) {
                    SummaryMode.SingleYear -> selectedYear.toString()
                    SummaryMode.SingleMonth -> IsoDates.monthOf(IsoDates.today())
                    SummaryMode.MultipleYears -> "all"
                }
                refresh()
            }
            is AppAction.SelectSummaryPeriod -> {
                summarySelection = action.selectionId
                if (summaryMode == SummaryMode.SingleYear) action.selectionId.toIntOrNull()?.let { selectedYear = it }
                refresh()
            }
            is AppAction.SelectBudgetMonth -> { selectedMonth = action.monthId; refresh() }
            is AppAction.UpdateBudget -> {
                val value = nonNegativeAmount(action.amount) ?: return
                mutate("Presupuesto actualizado") { current ->
                    current.copy(categorias = current.categorias.map {
                        if (it.nombre == action.categoryId) it.copy(presupuesto = value) else it
                    })
                }
            }
            is AppAction.UpdateInvestmentGoal -> {
                val value = nonNegativeAmount(action.amount) ?: return
                mutate("Objetivo actualizado") { it.copy(ajustes = it.ajustes.copy(objetivoInversion = value)) }
            }
            is AppAction.SelectAsset -> { selectedAsset = action.id; refresh() }
            is AppAction.SaveAsset -> saveAsset(action)
            is AppAction.DeleteAsset -> mutate("Activo borrado") { current ->
                current.copy(
                    activos = current.activos.filterNot { it.nombre == action.id },
                    movimientos = current.movimientos.map { if (it.activo == action.id) it.copy(activo = "") else it },
                    aportacionesGratis = current.aportacionesGratis.map { if (it.activo == action.id) it.copy(activo = "") else it },
                    periodicos = current.periodicos.map { if (it.activo == action.id) it.copy(activo = "") else it },
                )
            }
            is AppAction.AddPortfolioValue -> {
                val value = nonNegativeAmount(action.amount) ?: return
                if (!IsoDates.isValid(action.date)) return showError("La fecha no es válida.")
                mutate("Valoración añadida", MessageKind.Success) {
                    it.copy(historico = it.historico + Valoracion(action.date, value))
                }
            }
            is AppAction.DeletePortfolioValue -> mutate("Valoración borrada") { current ->
                current.copy(historico = current.historico.filterNot { it.id == action.id })
            }
            is AppAction.AddCashback -> {
                val value = requiredAmount(action.amount) ?: return
                if (!IsoDates.isValid(action.date)) return showError("La fecha no es válida.")
                mutate("Aportación gratis añadida", MessageKind.Success) {
                    it.copy(aportacionesGratis = it.aportacionesGratis + AportacionGratis(
                        fecha = action.date,
                        activo = action.assetId.orEmpty(),
                        concepto = action.concept,
                        importe = value,
                    ))
                }
            }
            is AppAction.DeleteCashback -> mutate("Aportación borrada") { current ->
                current.copy(aportacionesGratis = current.aportacionesGratis.filterNot { it.id == action.id })
            }
            AppAction.ImportTradeRepublic -> _effects.tryEmit(AppEffect.ChooseTradeRepublicPdf)
            is AppAction.SearchQuotes -> searchQuotes(action.assetId, action.query)
            is AppAction.SelectQuote -> selectQuote(action.assetId, action.symbol)
            AppAction.RefreshQuotes -> refreshQuotes(force = true, announce = true)
            is AppAction.SaveRecurring -> saveRecurring(action)
            is AppAction.ToggleRecurring -> mutate("Pago periódico actualizado") { current ->
                current.copy(periodicos = current.periodicos.map { recurring ->
                    if (recurring.id != action.id) recurring
                    else if (recurring.encendido) recurring.copy(encendido = false)
                    else Calculos.saltarLoPasado(recurring.copy(encendido = true), IsoDates.today())
                })
            }
            is AppAction.DeleteRecurring -> mutate("Pago periódico borrado") { current ->
                current.copy(periodicos = current.periodicos.filterNot { it.id == action.id })
            }
            is AppAction.SaveDebt -> saveDebt(action)
            is AppAction.UpdateDebtNote -> mutate("Nota guardada", MessageKind.Success) { current ->
                current.copy(deudas = current.deudas.map { if (it.id == action.id) it.copy(nota = action.note.trim()) else it })
            }
            is AppAction.SettleDebt -> settleDebt(action)
            is AppAction.DeleteDebt -> mutate("Deuda borrada") { current ->
                current.copy(deudas = current.deudas.filterNot { it.id == action.id })
            }
            is AppAction.UpdateInitialBalance -> {
                val value = SpanishFormat.parseNumber(action.amount) ?: return showError("Escribe un saldo válido.")
                mutate("Saldo inicial actualizado") { it.copy(ajustes = it.ajustes.copy(saldoInicial = value)) }
            }
            is AppAction.SaveCategory -> saveCategory(action)
            is AppAction.MoveCategory -> mutate("") { current ->
                val list = current.categorias.toMutableList()
                val index = list.indexOfFirst { it.nombre == action.id }
                val target = (index + action.direction).coerceIn(0, list.lastIndex)
                if (index >= 0 && index != target) list.add(target, list.removeAt(index))
                current.copy(categorias = list)
            }
            is AppAction.DeleteCategory -> mutate("Categoría borrada") { current ->
                current.copy(categorias = current.categorias.filterNot { it.nombre == action.id })
            }
            is AppAction.SetTheme -> mutate("") {
                it.copy(ajustes = it.ajustes.copy(tema = action.preference.toDomain()))
            }
            AppAction.ImportExcel -> _effects.tryEmit(AppEffect.ChooseExcelImport)
            AppAction.ExportExcel -> _effects.tryEmit(AppEffect.ChooseExcelExport("ContaXcell-${IsoDates.today()}.xlsx"))
            AppAction.SaveBackup -> viewModelScope.launch(Dispatchers.IO) {
                val file = store.backup("manual")
                withContext(Dispatchers.Main) {
                    message = UiMessage(if (file != null) "Copia guardada: ${file.name}" else "Todavía no hay datos que copiar.")
                    refresh()
                }
            }
            AppAction.RestoreBackup -> restoreLatestBackup()
            is AppAction.ChangePassword -> changePassword(action.current, action.new)
            AppAction.SignOut -> signOut()
        }
    }

    /** Called by MainActivity after Android's document picker returns a workbook. */
    fun importExcel(input: InputStream) {
        viewModelScope.launch {
            busy = true; refresh()
            runCatching {
                withContext(Dispatchers.IO) {
                    ExcelBookService().import(input)
                }
            }.onSuccess { imported ->
                replaceBook(
                    imported.book,
                    "antes-de-importar-excel",
                    listOf("Excel importado", *imported.warnings.toTypedArray()).joinToString(" · "),
                )
            }
                .onFailure { showError("No se ha podido importar el Excel: ${rootMessage(it)}") }
            busy = false; refresh()
        }
    }

    /** Called by MainActivity after Android's create-document picker returns a destination. */
    fun exportExcel(output: OutputStream) {
        viewModelScope.launch {
            busy = true; refresh()
            runCatching {
                withContext(Dispatchers.IO) {
                    ExcelBookService().export(output, book, selectedYear)
                }
            }.onSuccess { message = UiMessage("Excel exportado", MessageKind.Success) }
                .onFailure { showError("No se ha podido exportar el Excel: ${rootMessage(it)}") }
            busy = false; refresh()
        }
    }

    fun importTradeRepublic(input: InputStream) {
        viewModelScope.launch {
            busy = true; refresh()
            runCatching {
                withContext(Dispatchers.IO) {
                    val importer = TradeRepublicImporter()
                    val reading = importer.read(input)
                    val investment = book.categorias.firstOrNull { it.tipo == ContaXcellValues.INVERSION }?.nombre
                        ?: error("Crea primero una categoría de inversión.")
                    val income = book.categorias.firstOrNull { it.tipo == ContaXcellValues.INGRESO }?.nombre
                        ?: error("Crea primero una categoría de ingreso.")
                    val result = importer.apply(
                        book,
                        reading,
                        TradeRepublicOptions(investmentCategory = investment, incomeCategory = income),
                    )
                    Triple(result, reading.warnings, importer.manualContributions(book, reading).size)
                }
            }.onSuccess { (result, warnings, manualCount) ->
                val summary = result.summary
                val details = buildList {
                    add("${summary.purchases} compras")
                    if (summary.income > 0) add("${summary.income} ingresos")
                    if (summary.free > 0) add("${summary.free} bonificaciones")
                    if (summary.duplicates > 0) add("${summary.duplicates} duplicados omitidos")
                    if (manualCount > 0) add("$manualCount aportaciones manuales se conservaron")
                    addAll(warnings)
                }.joinToString(" · ")
                replaceBook(result.book, "antes-de-importar-trade-republic", details)
            }.onFailure { showError("No se ha podido importar el extracto: ${rootMessage(it)}") }
            busy = false; refresh()
        }
    }

    private suspend fun loadInitialState() {
        val loaded = withContext(Dispatchers.IO) { store.load() }
        val pending = Calculos.apuntarPendientes(loaded.libro, IsoDates.today())
        book = pending.libro
        if (pending.creados.isNotEmpty()) withContext(Dispatchers.IO) { store.save(book) }
        val session = sessions.read()
        auth = if (session.isSignedIn && !session.expired) {
            AuthUiState.SignedIn(session.username, session.serverUrl)
        } else {
            AuthUiState.Gate(
                previousSessionAvailable = session.username.isNotBlank(),
                defaultUser = session.username,
                defaultServer = session.serverUrl,
            )
        }
        if (loaded.startupNotice.isNotBlank()) message = UiMessage(loaded.startupNotice, MessageKind.Warning)
        if (pending.creados.isNotEmpty()) {
            message = UiMessage("Se han apuntado ${pending.creados.size} movimientos periódicos pendientes.", MessageKind.Success)
        }
        busy = false
        updateSyncUi()
        refresh()
        if (session.isSignedIn && !session.expired) syncNow()
    }

    private fun authenticate(register: Boolean, user: String, password: String, server: String, invitation: String) {
        auth = AuthUiState.Gate(defaultUser = user, defaultServer = server, busy = true)
        refresh()
        viewModelScope.launch {
            runCatching {
                if (register) authRepository.register(user, password, server, invitation)
                else authRepository.login(user, password, server)
            }.onSuccess { session ->
                auth = AuthUiState.SignedIn(session.username, session.serverUrl)
                message = UiMessage(if (register) "Cuenta creada" else "Sesión iniciada", MessageKind.Success)
                updateSyncUi()
                refresh()
                syncNow()
            }.onFailure { error ->
                val kind = (error as? AuthenticationException)?.kind
                auth = AuthUiState.Gate(
                    defaultUser = user,
                    defaultServer = server,
                    inviteRequired = kind == AuthenticationException.Kind.INVITATION_REQUIRED,
                    error = rootMessage(error),
                )
                refresh()
            }
        }
    }

    private fun syncNow() {
        viewModelScope.launch {
            syncUi = SyncUiState(SyncStatus.Pending, "Sincronizando…")
            refresh()
            when (syncEngine.syncNow()) {
                SyncResult.Current, is SyncResult.Uploaded -> Unit
                is SyncResult.Downloaded -> book = withContext(Dispatchers.IO) { store.load().libro }
                SyncResult.NoSession -> Unit
                SyncResult.Offline -> syncUi = SyncUiState(SyncStatus.Offline, "Sin conexión · cambios a salvo")
                SyncResult.SessionExpired -> syncUi = SyncUiState(SyncStatus.Error, "Sesión caducada")
                is SyncResult.Failed -> syncUi = SyncUiState(SyncStatus.Error, "No se ha podido sincronizar")
            }
            updateSyncUi(keepError = true)
            refresh()
            refreshQuotes(force = false, announce = false)
        }
    }

    private fun mutate(success: String, kind: MessageKind = MessageKind.Info, transform: (Libro) -> Libro) {
        viewModelScope.launch {
            mutationMutex.withLock {
                val next = transform(book).normalized()
                withContext(Dispatchers.IO) { store.save(next) }
                book = next
                syncEngine.markPending()
                if (success.isNotBlank()) message = UiMessage(success, kind)
                updateSyncUi()
                refresh()
                SyncScheduler.requestImmediate(getApplication())
            }
        }
    }

    private fun replaceBook(next: Libro, reason: String, notice: String) {
        viewModelScope.launch {
            mutationMutex.withLock {
                withContext(Dispatchers.IO) { store.replace(next.normalized(), reason) }
                book = next.normalized()
                syncEngine.markPending()
                message = UiMessage(notice, MessageKind.Success)
                updateSyncUi(); refresh(); SyncScheduler.requestImmediate(getApplication())
            }
        }
    }

    private fun saveAsset(action: AppAction.SaveAsset) {
        val initial = nonNegativeAmount(action.draft.initial) ?: return
        val market = nonNegativeAmount(action.draft.marketValue) ?: return
        val name = action.draft.name.trim()
        if (name.isEmpty()) return showError("Escribe un nombre para el activo.")
        if (book.activos.any { it.nombre.equals(name, true) && it.nombre != action.id }) {
            return showError("Ya existe un activo con ese nombre.")
        }
        val old = action.id
        val asset = Activo(
            nombre = name,
            aportacionInicial = initial,
            valorMercado = market,
            ultimaValoracion = if (action.draft.marketValue.isNotBlank()) IsoDates.today() else "",
            categoria = action.draft.category,
            simbolo = action.draft.quoteSymbol,
        )
        mutate("Activo guardado", MessageKind.Success) { current ->
            val assets = if (old == null) current.activos + asset else current.activos.map { if (it.nombre == old) asset.copy(isin = it.isin) else it }
            current.copy(
                activos = assets,
                movimientos = current.movimientos.map { if (old != null && it.activo == old) it.copy(activo = name) else it },
                aportacionesGratis = current.aportacionesGratis.map { if (old != null && it.activo == old) it.copy(activo = name) else it },
                periodicos = current.periodicos.map { if (old != null && it.activo == old) it.copy(activo = name) else it },
            )
        }
    }

    private fun searchQuotes(assetId: String, query: String) {
        quoteSearchAsset = assetId
        quoteSearchQuery = query
        quoteSearchError = null
        if (query.trim().length < 2) {
            quoteSearching = false
            quoteSearchResults = emptyList()
            refresh()
            return
        }
        quoteSearching = true
        refresh()
        viewModelScope.launch {
            runCatching { quoteRepository.search(query) }
                .onSuccess { quoteSearchResults = it }
                .onFailure {
                    quoteSearchResults = emptyList()
                    quoteSearchError = rootMessage(it)
                }
            quoteSearching = false
            refresh()
        }
    }

    private fun selectQuote(assetId: String, symbol: String?) {
        viewModelScope.launch {
            mutationMutex.withLock {
                val normalizedSymbol = symbol.orEmpty().trim().uppercase()
                val next = book.copy(
                    activos = book.activos.map { asset ->
                        if (asset.nombre == assetId) asset.copy(simbolo = normalizedSymbol) else asset
                    },
                    ajustes = book.ajustes.copy(preciosAlDia = ""),
                ).normalized()
                withContext(Dispatchers.IO) { store.save(next) }
                book = next
                syncEngine.markPending()
                quoteSearchAsset = null
                quoteSearchQuery = ""
                quoteSearchResults = emptyList()
                quoteSearchError = null
                val result = if (normalizedSymbol.isNotEmpty()) quoteSync.refresh(force = true) else null
                if (result is QuoteRefreshResult.Applied) syncEngine.markPending()
                message = UiMessage(
                    if (normalizedSymbol.isEmpty()) "Cotización automática desactivada"
                    else quoteResultMessage(result, "Cotización $normalizedSymbol vinculada"),
                    MessageKind.Success,
                )
                updateSyncUi()
                refresh()
                SyncScheduler.requestImmediate(getApplication())
            }
        }
    }

    private fun refreshQuotes(force: Boolean, announce: Boolean) {
        viewModelScope.launch {
            mutationMutex.withLock {
                val result = quoteSync.refresh(force)
                if (result is QuoteRefreshResult.Applied) {
                    syncEngine.markPending()
                    SyncScheduler.requestImmediate(getApplication())
                }
                if (announce) {
                    val error = result == QuoteRefreshResult.NoSession
                    message = UiMessage(
                        quoteResultMessage(result, "Cotizaciones actualizadas"),
                        if (error) MessageKind.Warning else MessageKind.Success,
                    )
                }
                updateSyncUi()
                refresh()
            }
        }
    }

    private fun quoteResultMessage(result: QuoteRefreshResult?, appliedPrefix: String) = when (result) {
        is QuoteRefreshResult.Applied -> "$appliedPrefix · ${result.result.newDates} precios nuevos"
        QuoteRefreshResult.AlreadyCurrent -> "Las cotizaciones ya están al día"
        QuoteRefreshResult.NoTrackedSymbols -> "No hay activos con cotización automática"
        QuoteRefreshResult.NoData -> "No se han recibido precios nuevos"
        QuoteRefreshResult.NoSession -> "Inicia sesión para actualizar cotizaciones"
        null -> appliedPrefix
    }

    private fun saveRecurring(action: AppAction.SaveRecurring) {
        val amount = requiredAmount(action.draft.amount) ?: return
        if (!IsoDates.isValid(action.draft.startDate)) return showError("La fecha de inicio no es válida.")
        if (action.draft.endDate.isNotBlank() && !IsoDates.isValid(action.draft.endDate)) return showError("La fecha de fin no es válida.")
        if (action.draft.name.isBlank()) return showError("Escribe un nombre.")
        val previous = book.periodicos.firstOrNull { it.id == action.id }
        val recurring = Periodico(
            id = previous?.id ?: newId(),
            nombre = action.draft.name,
            categoria = action.draft.categoryId,
            importe = amount,
            periodo = action.draft.cadence,
            desde = action.draft.startDate,
            hasta = action.draft.endDate,
            activo = action.draft.assetId.orEmpty(),
            encendido = previous?.encendido ?: true,
            apuntadoHasta = previous?.apuntadoHasta.orEmpty(),
        ).normalized()
        mutate("Pago periódico guardado", MessageKind.Success) { current ->
            current.copy(periodicos = if (previous == null) current.periodicos + recurring else current.periodicos.map { if (it.id == previous.id) recurring else it })
        }
    }

    private fun saveDebt(action: AppAction.SaveDebt) {
        val amount = requiredAmount(action.draft.amount) ?: return
        if (!IsoDates.isValid(action.draft.date)) return showError("La fecha no es válida.")
        if (action.draft.person.isBlank()) return showError("Escribe de quién es la deuda.")
        val previous = book.deuda(action.id.orEmpty())
        val debt = Deuda(
            id = previous?.id ?: newId(),
            quien = action.draft.person,
            sentido = action.draft.direction.toDomain(),
            importe = amount,
            fecha = action.draft.date,
            concepto = action.draft.concept,
            nota = action.draft.note,
            devuelto = minOf(previous?.devuelto ?: 0.0, amount),
        ).normalized()
        mutate("Deuda guardada", MessageKind.Success) { current ->
            current.copy(deudas = if (previous == null) current.deudas + debt else current.deudas.map { if (it.id == previous.id) debt else it })
        }
    }

    private fun settleDebt(action: AppAction.SettleDebt) {
        val debt = book.deuda(action.id) ?: return showError("Esa deuda ya no existe.")
        val amount = requiredAmount(action.draft.amount) ?: return
        val pending = Calculos.pendienteDe(debt)
        if (amount > pending) return showError("No puedes apuntar más de lo que queda: ${SpanishFormat.euros(pending)}.")
        if (!IsoDates.isValid(action.draft.date)) return showError("La fecha no es válida.")
        val category = if (action.draft.createMovement) {
            val selected = action.draft.categoryId?.let(book::categoria)
                ?: return showError("Elige una categoría para el movimiento.")
            val expected = if (debt.sentido == ContaXcellValues.ME_DEBEN) ContaXcellValues.INGRESO else ContaXcellValues.GASTO
            if (selected.tipo != expected) return showError("Elige una categoría de ${expected.lowercase()}.")
            selected
        } else null
        val payment = Calculos.anotarPago(debt, amount)
        mutate(
            if (Calculos.estaSaldada(payment.deuda)) "Deuda saldada" else "Pago anotado · quedan ${SpanishFormat.euros(Calculos.pendienteDe(payment.deuda))}",
            MessageKind.Success,
        ) { current ->
            val movement = category?.let {
                Movimiento(
                    fecha = action.draft.date,
                    descripcion = listOf(debt.quien, debt.concepto).filter(String::isNotBlank).joinToString(" · "),
                    categoria = it.nombre,
                    importe = payment.apuntado,
                    origen = debt.id,
                )
            }
            current.copy(
                deudas = current.deudas.map { if (it.id == debt.id) payment.deuda else it },
                movimientos = if (movement == null) current.movimientos else current.movimientos + movement,
            )
        }
    }

    private fun saveCategory(action: AppAction.SaveCategory) {
        val name = action.draft.name.trim()
        val budget = nonNegativeAmount(action.draft.budget) ?: return
        if (name.isEmpty()) return showError("Escribe un nombre para la categoría.")
        if (book.categorias.any { it.nombre.equals(name, true) && it.nombre != action.id }) return showError("Ya existe esa categoría.")
        val category = Categoria(name, action.draft.kind.toDomain(), budget)
        mutate("Categoría guardada", MessageKind.Success) { current ->
            if (action.id == null) current.copy(categorias = current.categorias + category)
            else current.copy(
                categorias = current.categorias.map { if (it.nombre == action.id) category else it },
                movimientos = current.movimientos.map { if (it.categoria == action.id) it.copy(categoria = name) else it },
                periodicos = current.periodicos.map { if (it.categoria == action.id) it.copy(categoria = name) else it },
            )
        }
    }

    private fun restoreLatestBackup() {
        viewModelScope.launch {
            val latest = withContext(Dispatchers.IO) { store.listBackups().firstOrNull() }
            if (latest == null) return@launch showError("No hay ninguna copia para restaurar.")
            runCatching { withContext(Dispatchers.IO) { store.restore(latest); store.load().libro } }
                .onSuccess { restored -> book = restored; syncEngine.markPending(); message = UiMessage("Copia restaurada", MessageKind.Success); updateSyncUi(); refresh() }
                .onFailure { showError("No se ha podido restaurar la copia: ${rootMessage(it)}") }
        }
    }

    private fun changePassword(current: String, new: String) {
        viewModelScope.launch {
            runCatching { authRepository.changePassword(current, new) }
                .onSuccess { message = UiMessage("Contraseña cambiada", MessageKind.Success); refresh() }
                .onFailure { showError(rootMessage(it)) }
        }
    }

    private fun signOut() {
        viewModelScope.launch {
            authRepository.logout()
            SyncScheduler.cancel(getApplication())
            auth = AuthUiState.Gate(defaultServer = com.contaxcell.app.data.sync.SyncSession.DEFAULT_SERVER_URL)
            syncUi = SyncUiState(SyncStatus.Offline, "Solo en este dispositivo")
            refresh()
        }
    }

    private fun refresh() {
        _state.value = buildUiState()
    }

    private fun buildUiState(): ContaXcellUiState {
        val hidden = book.ajustes.ocultarImportes
        val balanceRows = Calculos.conBalance(book)
        val currentMonth = Calculos.totalesDelMes(book, IsoDates.monthOf(IsoDates.today()))
        val years = Calculos.aniosConDatos(book)
        if (selectedYear !in years) selectedYear = years.first()
        val months = Calculos.mesesConDatos(book)
        if (selectedMonth !in months) selectedMonth = months.first()
        val categories = book.categorias.map { CategoryOption(it.nombre, it.nombre, it.tipo.toUiKind()) }
        val assets = book.activos.map { SelectableOption(it.nombre, it.nombre) }
        val allRows = balanceRows.asReversed().map { row ->
            val signed = if (row.tipo == ContaXcellValues.INGRESO) row.importe else -row.importe
            MovementRowUi(
                id = row.id, date = row.fecha, description = row.descripcion.ifBlank { "Sin concepto" },
                category = row.categoria, categoryId = row.categoria, kind = row.tipo.toUiKind(),
                amount = SpanishFormat.signedEuros(signed, hidden), rawAmount = SpanishFormat.number(row.importe),
                balance = SpanishFormat.euros(row.balance, hidden), asset = row.activo,
                assetId = row.activo.takeIf(String::isNotBlank),
            )
        }
        val filtered = allRows.filter { row ->
            (movementQuery.isBlank() || listOf(row.description, row.category, row.asset, row.amount).any { it.contains(movementQuery, true) }) &&
                (movementCategory == null || row.categoryId == movementCategory) &&
                (movementMonth == null || row.date.startsWith(movementMonth!!))
        }
        val summaryConfig = summaryConfiguration(years, months)
        val summary = Calculos.resumenPeriodo(book, summaryConfig.from, summaryConfig.to, summaryConfig.partition)
        val indicators = Calculos.indicadoresDe(book, summaryConfig.from, summaryConfig.to, summaryConfig.partition)
        val budget = Calculos.presupuestoDelMes(book, selectedMonth)
        val portfolio = Calculos.cartera(book)
        val chosenAsset = selectedAsset ?: portfolio.activos.firstOrNull()?.nombre
        selectedAsset = chosenAsset
        val chosenAssetLine = portfolio.activos.firstOrNull { it.nombre == chosenAsset }
        val chosenPurchases = chosenAsset?.let { Calculos.comprasDe(book, it) }.orEmpty()
        val quoteHistory = chosenAssetLine?.let { Calculos.cotizacionesDe(book, it.simbolo) }.orEmpty()
        val averagePaid = chosenAssetLine?.takeIf { it.titulos > 0 }?.let { it.totalAportado / it.titulos }
        val recurring = Calculos.resumenPeriodicos(book)
        val signedIn = auth as? AuthUiState.SignedIn
        return ContaXcellUiState(
            auth = auth,
            destination = destination,
            balance = SpanishFormat.euros(Calculos.saldoBanco(book), hidden),
            amountsHidden = hidden,
            theme = book.ajustes.tema.toUiTheme(),
            sync = syncUi,
            loading = busy,
            message = message,
            quickAdd = QuickAddUiState(
                categories = categories,
                assets = assets,
                today = IsoDates.today(),
                recent = allRows.take(6),
                monthMetrics = listOf(
                    metric("income", "Ingresos", currentMonth.ingresos, MetricTone.Positive, hidden),
                    metric("spend", "Gastos", currentMonth.gastos, MetricTone.Negative, hidden),
                    metric("saving", "Ahorro", currentMonth.ahorro, tone(currentMonth.ahorro), hidden),
                    metric("investment", "Inversión", currentMonth.inversion, MetricTone.Investment, hidden),
                ),
                cadences = ContaXcellValues.PERIODOS.toList(),
            ),
            movements = MovementsUiState(
                rows = filtered.take(movementLimit),
                categories = book.categorias.map { SelectableOption(it.nombre, it.nombre) },
                editCategories = categories,
                assets = assets,
                months = months.map { SelectableOption(it, IsoDates.monthName(it)) },
                query = movementQuery,
                categoryId = movementCategory,
                monthId = movementMonth,
                countLabel = "${filtered.size} ${if (filtered.size == 1) "movimiento" else "movimientos"}",
                totalsLabel = SpanishFormat.euros(filtered.sumOf { row -> SpanishFormat.parseNumber(row.rawAmount) ?: 0.0 }, hidden),
                canLoadMore = filtered.size > movementLimit,
            ),
            summary = SummaryUiState(
                year = selectedYear,
                availableYears = years,
                mode = summaryMode,
                selectionId = summaryConfig.selectionId,
                selectorOptions = summaryConfig.options,
                periodLabel = summaryConfig.label,
                trendTitle = when (summary.particion) { Calculos.POR_DIAS -> "Día a día"; Calculos.POR_ANIOS -> "Año a año"; else -> "Mes a mes" },
                showTrend = summary.tramos.any { it.hayDatos },
                metrics = if (summaryMode == SummaryMode.SingleMonth) listOf(
                    metric("income", "Ingresos del mes", summary.total.ingresos, MetricTone.Positive, hidden),
                    metric("spend", "Gastos del mes", summary.total.gastos, MetricTone.Negative, hidden),
                    metric("saving", "Ahorro del mes", summary.total.ahorro, tone(summary.total.ahorro), hidden),
                    metric("investment", "Inversión del mes", summary.total.inversion, MetricTone.Investment, hidden),
                    MetricUi(
                        "largest", "Mayor gasto",
                        indicators.mayorGasto?.let { SpanishFormat.euros(it.importe, hidden) } ?: "—",
                        indicators.mayorGasto?.descripcion.orEmpty(), MetricTone.Negative,
                    ),
                ) else listOf(
                    metric("balance", "Saldo", indicators.saldoBanco, tone(indicators.saldoBanco), hidden),
                    metric("saving", "Ahorro medio al mes", indicators.ahorroMedio, tone(indicators.ahorroMedio), hidden),
                    MetricUi("rate", "Tasa de ahorro", SpanishFormat.percentage(indicators.tasaAhorro), indicators.tramoMayorGasto),
                    MetricUi("cushion", "Colchón", "${SpanishFormat.decimal(indicators.mesesDeColchon)} meses", "Al gasto medio"),
                    metric("networth", "Patrimonio", indicators.patrimonio, tone(indicators.patrimonio), hidden),
                ),
                months = summary.meses.map { month -> MonthSummaryUi(
                    month.corto.replaceFirstChar(Char::uppercase), month.totales.ingresos, month.totales.gastos, month.totales.inversion,
                    SpanishFormat.euros(month.totales.ingresos, hidden), SpanishFormat.euros(month.totales.gastos, hidden),
                    SpanishFormat.euros(month.totales.ahorro, hidden), SpanishFormat.euros(month.totales.inversion, hidden),
                    SpanishFormat.euros(month.saldoFinal, hidden),
                ) },
                expenses = summary.gasto.filas.filter { it.importe != 0.0 }.map { CategoryShareUi(it.nombre, SpanishFormat.euros(it.importe, hidden), it.porcentaje.toFloat(), SpanishFormat.percentage(it.porcentaje)) },
                income = summary.ingreso.filas.filter { it.importe != 0.0 }.map { CategoryShareUi(it.nombre, SpanishFormat.euros(it.importe, hidden), it.porcentaje.toFloat(), SpanishFormat.percentage(it.porcentaje)) },
                empty = !summary.total.hayDatos,
            ),
            budgets = BudgetsUiState(
                monthId = selectedMonth,
                monthLabel = IsoDates.monthName(selectedMonth).replaceFirstChar(Char::uppercase),
                months = months.map { SelectableOption(it, IsoDates.monthName(it)) },
                rows = budget.filas.map { row -> BudgetRowUi(
                    categoryId = row.nombre,
                    category = row.nombre,
                    limit = SpanishFormat.euros(row.presupuesto, hidden),
                    rawLimit = SpanishFormat.number(row.presupuesto),
                    spent = SpanishFormat.euros(row.real, hidden),
                    available = SpanishFormat.euros(row.disponible, hidden),
                    consumedLabel = if (row.consumido.isFinite()) SpanishFormat.percentage(row.consumido) else "Sin límite",
                    fraction = row.consumido.coerceIn(0.0, 1.0).toFloat(),
                    overBudget = row.real > row.presupuesto,
                ) },
                metrics = listOf(
                    metric("planned", "Presupuestado", budget.presupuestado, MetricTone.Neutral, hidden),
                    metric("spent", "Gastado", budget.gastado, MetricTone.Negative, hidden),
                    metric("available", "Disponible", budget.disponible, tone(budget.disponible), hidden),
                    metric("margin", "Margen", budget.margen, tone(budget.margen), hidden),
                ),
                investmentMetrics = listOf(
                    metric("goal", "Objetivo", budget.objetivoInversion, MetricTone.Investment, hidden),
                    metric("contributed", "Aportado", budget.aportado, MetricTone.Investment, hidden),
                    metric("pending", "Pendiente", budget.pendiente, MetricTone.Neutral, hidden),
                ),
                investmentGoal = SpanishFormat.number(budget.objetivoInversion),
            ),
            investments = InvestmentsUiState(
                metrics = listOf(
                    metric("contributed", "Total aportado", portfolio.totalAportado, MetricTone.Investment, hidden),
                    metric("value", "Valor actual", portfolio.valorMercado, tone(portfolio.generado), hidden),
                    metric("generated", "Generado", portfolio.generado, tone(portfolio.generado), hidden),
                    MetricUi("return", "Rentabilidad", SpanishFormat.percentage(portfolio.rentabilidad), tone = tone(portfolio.generado)),
                    metric("free", "Aportado gratis", portfolio.aportadoGratis, MetricTone.Positive, hidden),
                ),
                assets = portfolio.activos.map { asset -> AssetUi(
                    id = asset.nombre,
                    name = asset.nombre,
                    category = asset.categoria,
                    initial = SpanishFormat.euros(asset.aportacionInicial, hidden),
                    fromBank = SpanishFormat.euros(asset.aportadoBanco, hidden),
                    free = SpanishFormat.euros(asset.aportadoGratis, hidden),
                    contributed = SpanishFormat.euros(asset.totalAportado, hidden),
                    marketValue = SpanishFormat.euros(asset.valorMercado, hidden),
                    generated = SpanishFormat.signedEuros(asset.generado, hidden),
                    returnLabel = SpanishFormat.percentage(asset.rentabilidad),
                    valuedAt = asset.ultimaValoracion.ifBlank { "Sin valorar" },
                    rawInitial = SpanishFormat.number(asset.aportacionInicial),
                    rawMarketValue = SpanishFormat.number(asset.valorMercado),
                    quoteSymbol = asset.simbolo,
                    quoteStatus = when {
                        asset.cotizado -> "Cotización automática"
                        asset.simbolo.isNotBlank() -> "Esperando la primera cotización"
                        else -> "Sin cotización automática"
                    },
                    latestQuoteDate = asset.ultimaValoracion.takeIf { asset.cotizado }.orEmpty(),
                    automaticallyQuoted = asset.cotizado,
                ) },
                categoryGroups = Calculos.porCategoria(portfolio).map { group -> InvestmentGroupUi(
                    group.categoria, group.activos.size, SpanishFormat.euros(group.totalAportado, hidden),
                    SpanishFormat.euros(group.valorMercado, hidden), SpanishFormat.signedEuros(group.generado, hidden), SpanishFormat.percentage(group.peso),
                ) },
                history = portfolio.historico.asReversed().map { point -> PortfolioHistoryUi(
                    point.id, point.fecha, point.aportado, point.valorMercado, SpanishFormat.euros(point.aportado, hidden),
                    SpanishFormat.euros(point.valorMercado, hidden), SpanishFormat.signedEuros(point.generado, hidden), SpanishFormat.percentage(point.rentabilidad),
                ) },
                cashback = book.aportacionesGratis.sortedByDescending { it.fecha }.map { CashbackUi(it.id, it.fecha, it.activo, it.concepto, SpanishFormat.euros(it.importe, hidden)) },
                purchases = chosenPurchases.map { purchase -> PurchaseUi(
                    id = purchase.id,
                    date = purchase.fecha,
                    invested = SpanishFormat.euros(purchase.importe, hidden),
                    units = SpanishFormat.number(purchase.titulos, 6),
                    paidPrice = if (purchase.titulos > 0) SpanishFormat.euros(purchase.precioPagado, hidden) else "—",
                    currentValue = if (purchase.precioHoy > 0) SpanishFormat.euros(purchase.valorHoy, hidden) else "—",
                    generated = if (purchase.precioHoy > 0) SpanishFormat.signedEuros(purchase.generado, hidden) else "—",
                    returnLabel = if (purchase.precioHoy > 0) SpanishFormat.percentage(purchase.rentabilidad) else "—",
                    quoteAtPurchase = purchase.quoteAtPurchase?.let { SpanishFormat.euros(it, hidden) }.orEmpty(),
                    quoteToday = purchase.quoteToday?.let { SpanishFormat.euros(it, hidden) }.orEmpty(),
                    quoteChangeLabel = purchase.quoteChange?.let(SpanishFormat::percentage).orEmpty(),
                ) },
                selectedAssetId = chosenAsset,
                quoteSearch = QuoteSearchUiState(
                    assetId = quoteSearchAsset,
                    query = quoteSearchQuery,
                    searching = quoteSearching,
                    results = quoteSearchResults.map { result -> QuoteSearchResultUi(
                        symbol = result.symbol,
                        name = result.name,
                        exchange = result.exchange,
                        currency = result.currency,
                        latestPrice = result.price.takeIf { it > 0 }?.let { SpanishFormat.euros(it, hidden) }.orEmpty(),
                    ) },
                    error = quoteSearchError,
                ),
                quoteHistory = quoteHistory.map { quote -> QuotePointUi(
                    date = quote.fecha,
                    value = quote.precio,
                    valueLabel = SpanishFormat.euros(quote.precio, hidden),
                ) },
                quoteAveragePaid = averagePaid,
                quoteAveragePaidLabel = averagePaid?.let { SpanishFormat.euros(it, hidden) }.orEmpty(),
                quoteStatus = when {
                    chosenAssetLine == null -> ""
                    chosenAssetLine.cotizado -> "Último cierre: ${chosenAssetLine.ultimaValoracion}"
                    chosenAssetLine.simbolo.isNotBlank() -> "Sin precios guardados todavía"
                    else -> "Vincula una cotización para valorar automáticamente"
                },
            ),
            recurring = RecurringUiState(
                metrics = listOf(
                    MetricUi("active", "Activos", recurring.encendidos.toString()),
                    metric("expense", "Gasto mensual", recurring.gasto, MetricTone.Negative, hidden),
                    metric("income", "Ingreso mensual", recurring.ingreso, MetricTone.Positive, hidden),
                    metric("investment", "Inversión mensual", recurring.inversion, MetricTone.Investment, hidden),
                ),
                rows = book.periodicos.map { item -> RecurringRowUi(
                    item.id, item.nombre, item.categoria, item.categoria, SpanishFormat.euros(item.importe, hidden),
                    SpanishFormat.number(item.importe), item.periodo, Calculos.proximoVencimiento(item), item.desde, item.hasta,
                    item.activo.takeIf(String::isNotBlank), item.encendido, item.encendido && !Calculos.estaVigente(item), book.tipoDe(item.categoria).toUiKind(),
                ) },
                categories = categories,
                assets = assets,
                cadences = ContaXcellValues.PERIODOS.toList(),
            ),
            debts = DebtsUiState(
                metrics = Calculos.resumenDeudas(book).let { debts -> listOf(
                    metric("owed", "Te deben", debts.teDeben, MetricTone.Positive, hidden),
                    metric("owe", "Debes", debts.debes, MetricTone.Negative, hidden),
                    metric("net", "Neto", debts.neto, tone(debts.neto), hidden),
                    MetricUi("open", "Sin saldar", debts.abiertas.toString(), "${debts.saldadas} saldadas"),
                ) },
                rows = book.deudas.sortedWith(compareBy<Deuda> { Calculos.estaSaldada(it) }.thenBy { it.quien.lowercase() }.thenBy { it.fecha }).map { debt ->
                    val pending = Calculos.pendienteDe(debt)
                    DebtRowUi(
                        id = debt.id,
                        person = debt.quien,
                        concept = debt.concepto,
                        date = debt.fecha,
                        total = SpanishFormat.euros(debt.importe, hidden),
                        rawTotal = SpanishFormat.number(debt.importe),
                        pending = if (pending > 0) SpanishFormat.euros(pending, hidden) else "—",
                        rawPending = SpanishFormat.number(pending),
                        note = debt.nota,
                        direction = debt.sentido.toUiDebtDirection(),
                        settled = Calculos.estaSaldada(debt),
                    )
                },
                people = Calculos.deudasPorPersona(book).map { person -> DebtPersonUi(
                    person.quien, person.cuantas, SpanishFormat.signedEuros(person.neto, hidden), tone(person.neto),
                ) },
                categories = categories,
                today = IsoDates.today(),
            ),
            settings = SettingsUiState(
                initialBalance = SpanishFormat.number(book.ajustes.saldoInicial),
                bankMetrics = listOf(
                    metric("initial", "Saldo inicial", book.ajustes.saldoInicial, MetricTone.Neutral, hidden),
                    metric("current", "Saldo actual", Calculos.saldoBanco(book), tone(Calculos.saldoBanco(book)), hidden),
                ),
                categories = book.categorias.map { category -> CategorySettingsUi(
                    id = category.nombre,
                    name = category.nombre,
                    kind = category.tipo.toUiKind(),
                    budget = SpanishFormat.euros(category.presupuesto, hidden),
                    rawBudget = SpanishFormat.number(category.presupuesto),
                    uses = book.movimientos.count { it.categoria == category.nombre },
                ) },
                account = AccountUi(
                    signedIn = signedIn?.user?.isNotBlank() == true,
                    user = signedIn?.user.orEmpty(), server = signedIn?.server.orEmpty(), syncDetail = syncUi.label,
                    sessionExpired = syncUi.status == SyncStatus.Error && syncUi.label.contains("caducada", true),
                ),
                appVersion = BuildConfig.VERSION_NAME,
                dataLocation = "Almacenamiento privado · ${store.javaClass.simpleName}",
            ),
        )
    }

    private fun summaryConfiguration(years: List<Int>, months: List<String>): SummaryConfiguration {
        val latestYear = years.maxOrNull() ?: IsoDates.today().take(4).toInt()
        val oldestYear = years.minOrNull() ?: latestYear
        return when (summaryMode) {
            SummaryMode.SingleYear -> {
                val chosen = summarySelection.toIntOrNull()?.takeIf { it in years } ?: selectedYear.takeIf { it in years } ?: latestYear
                selectedYear = chosen
                summarySelection = chosen.toString()
                SummaryConfiguration(
                    "$chosen-01", "$chosen-12", Calculos.POR_MESES, chosen.toString(), chosen.toString(),
                    years.map { SelectableOption(it.toString(), it.toString()) },
                )
            }
            SummaryMode.SingleMonth -> {
                val chosen = summarySelection.takeIf { it in months } ?: months.firstOrNull() ?: IsoDates.monthOf(IsoDates.today())
                summarySelection = chosen
                SummaryConfiguration(
                    chosen, chosen, Calculos.POR_DIAS, chosen,
                    IsoDates.monthName(chosen).replaceFirstChar(Char::uppercase),
                    months.map { SelectableOption(it, IsoDates.monthName(it).replaceFirstChar(Char::uppercase)) },
                )
            }
            SummaryMode.MultipleYears -> {
                val span = latestYear - oldestYear + 1
                val choices = buildList {
                    add(SelectableOption("all", "Todo"))
                    (2..5).filter { it < span }.forEach { add(SelectableOption(it.toString(), "Últimos $it años")) }
                }
                val chosenId = summarySelection.takeIf { value -> choices.any { it.id == value } } ?: "all"
                summarySelection = chosenId
                val count = chosenId.toIntOrNull()
                val first = if (count == null) oldestYear else maxOf(oldestYear, latestYear - count + 1)
                SummaryConfiguration(
                    "$first-01", "$latestYear-12",
                    if (first == latestYear) Calculos.POR_MESES else Calculos.POR_ANIOS,
                    chosenId, if (first == latestYear) latestYear.toString() else "$first-$latestYear", choices,
                )
            }
        }
    }

    private fun createSyncEngine() = SyncEngine(
        api, sessions,
        object : SyncBookStore {
            override suspend fun read(): Libro = withContext(Dispatchers.IO) { store.load().libro }
            override suspend fun replace(book: Libro, reason: String) = withContext(Dispatchers.IO) { store.replace(book, reason) }
            override suspend fun backup(book: Libro, reason: String): String? = withContext(Dispatchers.IO) {
                store.backup(book, reason)?.absolutePath
            }
        },
        SyncEventSink { event ->
            when (event) {
                SyncEvent.Synced -> syncUi = SyncUiState(SyncStatus.Synced, "Al día")
                SyncEvent.Offline -> syncUi = SyncUiState(SyncStatus.Offline, "Sin conexión · cambios a salvo")
                SyncEvent.SessionExpired -> syncUi = SyncUiState(SyncStatus.Error, "Sesión caducada")
                is SyncEvent.ConflictBackedUp -> message = UiMessage("Había cambios de otro dispositivo; se ha guardado una copia.", MessageKind.Warning)
                is SyncEvent.Downloaded -> {
                    book = withContext(Dispatchers.IO) { store.load().libro }
                    message = UiMessage("Datos descargados de tu cuenta", MessageKind.Success)
                    refresh()
                }
                is SyncEvent.UnexpectedServerResponse -> syncUi = SyncUiState(SyncStatus.Error, "Error del servidor (${event.statusCode})")
            }
        },
    )

    private suspend fun updateSyncUi(keepError: Boolean = false) {
        if (keepError && syncUi.status in setOf(SyncStatus.Error, SyncStatus.Offline)) return
        val session = sessions.read()
        syncUi = when {
            !session.isSignedIn -> SyncUiState(SyncStatus.Offline, "Solo en este dispositivo")
            session.expired -> SyncUiState(SyncStatus.Error, "Sesión caducada")
            session.pending -> SyncUiState(SyncStatus.Pending, "Pendiente · a salvo en el teléfono")
            else -> SyncUiState(SyncStatus.Synced, "Al día")
        }
    }

    private fun metric(id: String, label: String, value: Double, tone: MetricTone, hidden: Boolean) =
        MetricUi(id, label, SpanishFormat.euros(value, hidden), tone = tone)

    private fun tone(value: Double) = when {
        value > 0 -> MetricTone.Positive
        value < 0 -> MetricTone.Negative
        else -> MetricTone.Neutral
    }

    private fun requiredAmount(text: String): Double? {
        val value = SpanishFormat.parseNumber(text)
        if (value == null || value <= 0) { showError("Escribe un importe mayor que cero."); return null }
        return value
    }

    private fun nonNegativeAmount(text: String): Double? {
        if (text.isBlank()) return 0.0
        val value = SpanishFormat.parseNumber(text)
        if (value == null || value < 0) { showError("Escribe un importe válido."); return null }
        return value
    }

    private fun showError(text: String) {
        message = UiMessage(text, MessageKind.Error)
        refresh()
    }

    private fun rootMessage(error: Throwable): String {
        var current = error
        while (current.cause != null) current = current.cause!!
        return current.message ?: "Error inesperado"
    }
}

private fun String.toUiKind() = when (this) {
    ContaXcellValues.INGRESO -> MovementKind.Income
    ContaXcellValues.INVERSION -> MovementKind.Investment
    else -> MovementKind.Expense
}

private fun MovementKind.toDomain() = when (this) {
    MovementKind.Income -> ContaXcellValues.INGRESO
    MovementKind.Investment -> ContaXcellValues.INVERSION
    MovementKind.Expense -> ContaXcellValues.GASTO
}

private fun String.toUiTheme() = when (this) {
    "claro" -> ThemePreference.Light
    "oscuro" -> ThemePreference.Dark
    else -> ThemePreference.System
}

private fun ThemePreference.toDomain() = when (this) {
    ThemePreference.Light -> "claro"
    ThemePreference.Dark -> "oscuro"
    ThemePreference.System -> "auto"
}

private fun DebtDirection.toDomain() = when (this) {
    DebtDirection.OwedToMe -> ContaXcellValues.ME_DEBEN
    DebtDirection.IOwe -> ContaXcellValues.DEBO
}

private fun String.toUiDebtDirection() = if (this == ContaXcellValues.DEBO) DebtDirection.IOwe else DebtDirection.OwedToMe

private data class SummaryConfiguration(
    val from: String,
    val to: String,
    val partition: String,
    val selectionId: String,
    val label: String,
    val options: List<SelectableOption>,
)
