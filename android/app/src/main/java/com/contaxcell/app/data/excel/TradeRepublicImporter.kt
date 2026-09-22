package com.contaxcell.app.data.excel

import com.contaxcell.app.domain.Activo
import com.contaxcell.app.domain.AportacionGratis
import com.contaxcell.app.domain.ContaXcellValues
import com.contaxcell.app.domain.DomainNumbers
import com.contaxcell.app.domain.IsoDates
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.nio.charset.StandardCharsets
import java.util.zip.InflaterInputStream
import kotlin.math.abs

class NotTradeRepublicStatementException(message: String) : Exception(message)

enum class TradeRepublicEntryKind { PURCHASE, INCOME, FREE }

data class TradeRepublicEntry(
    val kind: TradeRepublicEntryKind,
    val date: String,
    val concept: String,
    val amount: Double,
    val isin: String = "",
    val assetName: String = "",
    val titles: Double = 0.0,
) {
    val price: Double get() = if (titles > 0) amount / titles else 0.0
}

data class TradeRepublicReading(
    val entries: List<TradeRepublicEntry>,
    val from: String = entries.minOfOrNull { it.date }.orEmpty(),
    val until: String = entries.maxOfOrNull { it.date }.orEmpty(),
    val warnings: List<String> = emptyList(),
) {
    val purchases get() = entries.filter { it.kind == TradeRepublicEntryKind.PURCHASE }
    val income get() = entries.filter { it.kind == TradeRepublicEntryKind.INCOME }
    val free get() = entries.filter { it.kind == TradeRepublicEntryKind.FREE }
}

data class TradeRepublicOptions(
    val investmentCategory: String,
    val incomeCategory: String,
    val assetCategory: String = "",
    val rewardCategory: String = "",
    val replaceManualMovementIds: Set<String> = emptySet(),
)

data class TradeRepublicApplySummary(
    val purchases: Int = 0,
    val income: Int = 0,
    val duplicates: Int = 0,
    val newAssets: List<String> = emptyList(),
    val invested: Double = 0.0,
    val received: Double = 0.0,
    val replaced: Int = 0,
    val replacedAmount: Double = 0.0,
    val free: Int = 0,
    val gifted: Double = 0.0,
    val corrected: Int = 0,
)

data class TradeRepublicApplyResult(
    val book: Libro,
    val summary: TradeRepublicApplySummary,
)

class TradeRepublicImporter {
    fun read(input: InputStream): TradeRepublicReading = read(input.readBytes())

    fun read(pdf: ByteArray): TradeRepublicReading = readLines(extractLines(pdf))

    /** Public for preview/tests and for PDFs already converted to text by a document provider. */
    fun readLines(lines: List<String>): TradeRepublicReading {
        val entries = mutableListOf<TradeRepublicEntry>()
        val warnings = mutableListOf<String>()
        fun row(index: Int) = lines.getOrElse(index) { "" }
        lines.forEachIndexed { index, line ->
            when {
                PURCHASE_MARK in line -> {
                    parsePurchase(line, row(index + 1), row(index + 2))?.let(entries::add)
                        ?: warnings.add("No se ha entendido una compra: ${line.take(60)}…")
                }
                INCOME_MARKS.keys.any { it in line } -> {
                    val marker = INCOME_MARKS.keys.first { it in line }
                    parseIncome(line, row(index - 1), row(index + 1), INCOME_MARKS.getValue(marker))
                        ?.let(entries::add)
                        ?: warnings.add("No se ha entendido un ingreso: ${line.take(60)}…")
                }
            }
        }
        return TradeRepublicReading(matchReinvestedRewards(entries), warnings = warnings)
    }

    /** Manual, title-less investment movements that overlap the statement's covered months. */
    fun manualContributions(book: Libro, reading: TradeRepublicReading): List<Movimiento> {
        val dates = reading.purchases.map { it.date }.sorted()
        if (dates.isEmpty()) return emptyList()
        val from = dates.first().take(7) + "-01"
        val until = dates.last().take(7) + "-31"
        val names = reading.purchases.map { entry ->
            book.activoPorIsin(entry.isin)?.nombre
                ?: book.activo(entry.assetName)?.nombre
                ?: entry.assetName
        }.toSet()
        return book.movimientos.filter { movement ->
            book.tipoDe(movement.categoria) == ContaXcellValues.INVERSION &&
                movement.titulos == 0.0 && movement.fecha in from..until &&
                (movement.activo.isBlank() || movement.activo in names)
        }
    }

    fun apply(book: Libro, reading: TradeRepublicReading, options: TradeRepublicOptions): TradeRepublicApplyResult {
        var movements = book.movimientos.toMutableList()
        var assets = book.activos.toMutableList()
        var freeEntries = book.aportacionesGratis.toMutableList()
        var summary = TradeRepublicApplySummary()

        if (options.replaceManualMovementIds.isNotEmpty()) {
            val removed = movements.filter { it.id in options.replaceManualMovementIds }
            movements.removeAll(removed.toSet())
            summary = summary.copy(
                replaced = removed.size,
                replacedAmount = money(removed.sumOf { it.importe }),
            )
        }

        (reading.purchases + reading.free).forEach { entry ->
            var assetIndex = assets.indexOfFirst {
                (entry.isin.isNotBlank() && it.isin.equals(entry.isin, ignoreCase = true)) ||
                    it.nombre == entry.assetName
            }
            val asset: Activo
            if (assetIndex < 0) {
                asset = Activo(
                    nombre = freeAssetName(assets, entry.assetName),
                    isin = entry.isin,
                    categoria = options.assetCategory,
                )
                assets.add(asset)
                assetIndex = assets.lastIndex
                summary = summary.copy(newAssets = summary.newAssets + asset.nombre)
            } else {
                val existing = assets[assetIndex]
                asset = if (existing.isin.isBlank() && entry.isin.isNotBlank()) {
                    existing.copy(isin = entry.isin).also { assets[assetIndex] = it }
                } else existing
            }

            if (entry.kind == TradeRepublicEntryKind.FREE) {
                val oldIndex = movements.indexOfFirst {
                    it.fecha == entry.date && abs(it.importe - entry.amount) < MONEY_EPSILON &&
                        abs(it.titulos - entry.titles) < TITLE_EPSILON && it.titulos > 0
                }
                if (oldIndex >= 0) {
                    movements.removeAt(oldIndex)
                    summary = summary.copy(corrected = summary.corrected + 1)
                }
                val duplicate = freeEntries.any {
                    it.fecha == entry.date && abs(it.importe - entry.amount) < MONEY_EPSILON &&
                        it.activo == asset.nombre
                }
                if (duplicate) {
                    summary = summary.copy(duplicates = summary.duplicates + 1)
                } else {
                    freeEntries.add(
                        AportacionGratis(
                            fecha = entry.date,
                            activo = asset.nombre,
                            concepto = entry.concept,
                            importe = entry.amount,
                            titulos = entry.titles,
                        ),
                    )
                    summary = summary.copy(
                        free = summary.free + 1,
                        gifted = money(summary.gifted + entry.amount),
                    )
                }
            } else if (alreadyPresent(movements, entry)) {
                summary = summary.copy(duplicates = summary.duplicates + 1)
            } else {
                movements.add(
                    Movimiento(
                        fecha = entry.date,
                        descripcion = entry.concept,
                        categoria = options.investmentCategory,
                        importe = entry.amount,
                        activo = asset.nombre,
                        titulos = entry.titles,
                    ),
                )
                summary = summary.copy(
                    purchases = summary.purchases + 1,
                    invested = money(summary.invested + entry.amount),
                )
            }
        }

        reading.income.forEach { entry ->
            if (alreadyPresent(movements, entry)) {
                summary = summary.copy(duplicates = summary.duplicates + 1)
            } else {
                val category = if (entry.concept == REWARD_CONCEPT && options.rewardCategory.isNotBlank()) {
                    options.rewardCategory
                } else options.incomeCategory
                movements.add(
                    Movimiento(
                        fecha = entry.date,
                        descripcion = entry.concept,
                        categoria = category,
                        importe = entry.amount,
                    ),
                )
                summary = summary.copy(
                    income = summary.income + 1,
                    received = money(summary.received + entry.amount),
                )
            }
        }

        return TradeRepublicApplyResult(
            book.copy(movimientos = movements, activos = assets, aportacionesGratis = freeEntries).normalized(),
            summary,
        )
    }

    internal fun extractLines(pdf: ByteArray): List<String> {
        val streams = compressedStreams(pdf).mapNotNull(::inflate)
        val characterMap = unicodeMap(streams)
        if (characterMap.isEmpty()) {
            throw NotTradeRepublicStatementException("El PDF no trae la tabla de letras necesaria.")
        }
        val lines = mutableListOf<String>()
        streams.filter { "BT" in it && "Tf" in it }.forEach { page ->
            var x = 0.0
            var y = 0.0
            val chunks = mutableListOf<Triple<Double, Double, String>>()
            PDF_TOKEN.findAll(page).forEach { match ->
                if (match.groups[1] != null) {
                    x = match.groupValues[1].toDoubleOrNull() ?: x
                    y = match.groupValues[2].toDoubleOrNull() ?: y
                } else {
                    val decoded = decodeChunk(match.value, characterMap).trim()
                    if (decoded.isNotEmpty()) chunks.add(Triple(roundTenth(y), x, decoded))
                }
            }
            chunks.map { it.first }.distinct().sortedDescending().forEach { level ->
                lines += chunks.filter { it.first == level }
                    .sortedBy { it.second }
                    .joinToString("  |  ") { it.third }
            }
        }
        return lines
    }

    private fun parsePurchase(line: String, next: String, third: String): TradeRepublicEntry? {
        val day = DAY.find(line) ?: return null
        val year = YEAR.find(third)?.groupValues?.get(1) ?: return null
        val amount = EUROS.find(next)?.groupValues?.get(1)?.let(::euros) ?: return null
        val titles = TITLES.find(third)?.groupValues?.get(1)?.toDoubleOrNull()?.let(DomainNumbers::titles)
            ?.takeIf { it > 0 } ?: return null
        val description = "${withoutFirstColumn(line)} ${withoutFirstColumn(third)}"
        return TradeRepublicEntry(
            TradeRepublicEntryKind.PURCHASE,
            date(day, year),
            "Compra del plan de inversión",
            amount,
            ISIN.find(line)?.groupValues?.get(1).orEmpty(),
            shortName(description),
            titles,
        )
    }

    private fun parseIncome(
        line: String,
        previous: String,
        next: String,
        concept: String,
    ): TradeRepublicEntry? {
        val day = DAY.find(line) ?: DAY.find(previous) ?: return null
        val year = FULL_YEAR.find(next) ?: FULL_YEAR.find(line) ?: FULL_YEAR.find(previous) ?: return null
        val amount = EUROS.find(line)?.groupValues?.get(1)?.let(::euros) ?: return null
        return TradeRepublicEntry(
            TradeRepublicEntryKind.INCOME,
            date(day, year.groupValues[1]),
            concept,
            amount,
        )
    }

    private fun matchReinvestedRewards(input: List<TradeRepublicEntry>): List<TradeRepublicEntry> {
        val entries = input.toMutableList()
        val rewards = entries.filter { it.kind == TradeRepublicEntryKind.INCOME && it.concept == REWARD_CONCEPT }
        rewards.forEach { reward ->
            val limit = IsoDates.plusDays(reward.date, 10).ifEmpty { reward.date }
            val purchaseIndex = entries.indexOfFirst {
                it.kind == TradeRepublicEntryKind.PURCHASE && abs(it.amount - reward.amount) < MONEY_EPSILON &&
                    it.date in reward.date..limit
            }
            if (purchaseIndex >= 0) {
                entries[purchaseIndex] = entries[purchaseIndex].copy(
                    kind = TradeRepublicEntryKind.FREE,
                    concept = reward.concept,
                )
                entries.remove(reward)
            }
        }
        return entries
    }

    private fun alreadyPresent(movements: List<Movimiento>, entry: TradeRepublicEntry): Boolean =
        movements.any {
            if (it.fecha != entry.date || abs(it.importe - entry.amount) > MONEY_EPSILON) false
            else if (entry.titles > 0) abs(it.titulos - entry.titles) < TITLE_EPSILON
            else it.descripcion == entry.concept
        }

    private fun compressedStreams(pdf: ByteArray): List<ByteArray> {
        val marker = "stream".toByteArray(StandardCharsets.ISO_8859_1)
        val endMarker = "endstream".toByteArray(StandardCharsets.ISO_8859_1)
        val streams = mutableListOf<ByteArray>()
        var cursor = 0
        while (cursor < pdf.size) {
            val startMarker = pdf.indexOf(marker, cursor)
            if (startMarker < 0) break
            var start = startMarker + marker.size
            if (start < pdf.size && pdf[start] == '\r'.code.toByte()) start++
            if (start < pdf.size && pdf[start] == '\n'.code.toByte()) start++
            val end = pdf.indexOf(endMarker, start)
            if (end < 0) break
            streams += pdf.copyOfRange(start, end)
            cursor = end + endMarker.size
        }
        return streams
    }

    private fun inflate(bytes: ByteArray): String? = runCatching {
        InflaterInputStream(ByteArrayInputStream(bytes)).use { inflater ->
            val output = ByteArrayOutputStream()
            inflater.copyTo(output)
            output.toString(StandardCharsets.ISO_8859_1.name())
        }
    }.getOrNull()

    private fun unicodeMap(streams: List<String>): Map<Int, Char> {
        val map = mutableMapOf<Int, Char>()
        streams.filter { "beginbfrange" in it }.forEach { stream ->
            BFRANGE.findAll(stream).forEach { match ->
                val from = match.groupValues[1].toInt(16)
                val until = match.groupValues[2].toInt(16)
                val destination = match.groupValues[3].toInt(16)
                repeat(minOf(until - from + 1, 512)) { offset ->
                    map[from + offset] = (destination + offset).toChar()
                }
            }
        }
        return map
    }

    private fun decodeChunk(chunk: String, map: Map<Int, Char>): String {
        var value = chunk.removePrefix("(").removeSuffix(")")
            .replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        var bytes = value.toByteArray(StandardCharsets.ISO_8859_1)
        if (bytes.size % 2 != 0) bytes += byteArrayOf(0)
        return buildString {
            for (index in bytes.indices step 2) {
                val code = (bytes[index].toInt() and 0xff) * 256 + (bytes[index + 1].toInt() and 0xff)
                map[code]?.let(::append)
            }
        }
    }

    private fun date(day: MatchResult, year: String): String {
        val month = MONTHS.getValue(day.groupValues[2])
        return "%s-%02d-%02d".format(year, month, day.groupValues[1].toInt())
    }

    private fun euros(value: String) = money(value.replace(".", "").replace(",", ".").toDouble())
    private fun money(value: Double) = DomainNumbers.money(value)
    private fun withoutFirstColumn(value: String) = value.substringAfter('|', value).trim()

    private fun shortName(description: String): String {
        KNOWN_INDEXES.firstOrNull { description.contains(it, ignoreCase = true) }?.let { return it }
        val cleaned = description.substringBefore("quantity")
            .replace(ISIN, " ")
            .replace(PURCHASE_MARK, " ")
            .substringAfterLast(" - ")
            .replace(Regex("\\b(UCITS|ETF|USD|EUR|Acc|Dist|plc|III|II)\\b"), " ")
            .replace(Regex("[(),]"), " ")
            .trim().replace(Regex("\\s+"), " ")
        return cleaned.take(40).ifEmpty { "Fondo" }
    }

    private fun freeAssetName(assets: List<Activo>, proposed: String): String {
        val base = proposed.ifBlank { "Fondo" }
        if (assets.none { it.nombre == base }) return base
        return (2 until 50).firstNotNullOfOrNull { number ->
            "$base ($number)".takeIf { candidate -> assets.none { it.nombre == candidate } }
        } ?: base
    }

    private fun roundTenth(value: Double) = kotlin.math.round(value * 10.0) / 10.0

    private fun ByteArray.indexOf(needle: ByteArray, start: Int): Int {
        if (needle.isEmpty()) return start
        for (index in start..size - needle.size) {
            if (needle.indices.all { this[index + it] == needle[it] }) return index
        }
        return -1
    }

    private companion object {
        const val PURCHASE_MARK = "Savings plan execution"
        const val INTEREST_CONCEPT = "Intereses de Trade Republic"
        const val REWARD_CONCEPT = "Bonificación de Trade Republic"
        const val MONEY_EPSILON = 0.005
        const val TITLE_EPSILON = 0.0000005
        val INCOME_MARKS = mapOf(
            "Interest payment" to INTEREST_CONCEPT,
            "Cash reward allocation" to REWARD_CONCEPT,
            "Saveback cash reward" to REWARD_CONCEPT,
        )
        val MONTHS = mapOf(
            "ene" to 1, "feb" to 2, "mar" to 3, "abr" to 4,
            "may" to 5, "jun" to 6, "jul" to 7, "ago" to 8,
            "sept" to 9, "sep" to 9, "oct" to 10, "nov" to 11, "dic" to 12,
        )
        val KNOWN_INDEXES = listOf(
            "MSCI World", "MSCI Emerging Markets", "S&P 500", "Nasdaq",
            "FTSE All-World", "Euro Stoxx 50", "STOXX Europe 600",
            "MSCI ACWI", "MSCI Europe", "MSCI USA",
        )
        val DAY = Regex("\\b(\\d{1,2}) (${MONTHS.keys.joinToString("|")})\\b")
        val YEAR = Regex("^\\s*(\\d{4})\\b")
        val FULL_YEAR = Regex("\\b(20\\d{2})\\b")
        val ISIN = Regex("\\b([A-Z]{2}[A-Z0-9]{9}\\d)\\b")
        val EUROS = Regex("([\\d.]+,\\d{2})")
        val TITLES = Regex("quantity:\\s*([\\d.]+)")
        val BFRANGE = Regex("<([0-9A-Fa-f]+)><([0-9A-Fa-f]+)><([0-9A-Fa-f]+)>")
        val PDF_TOKEN = Regex("1 0 0 1 ([\\d.]+) ([\\d.]+) Tm|\\((?:[^()\\\\]|\\\\.)*\\)")
    }
}
