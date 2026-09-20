package com.contaxcell.app.data.excel

import com.contaxcell.app.domain.Activo
import com.contaxcell.app.domain.Ajustes
import com.contaxcell.app.domain.AportacionGratis
import com.contaxcell.app.domain.Categoria
import com.contaxcell.app.domain.ContaXcellValues
import com.contaxcell.app.domain.DomainNumbers
import com.contaxcell.app.domain.IsoDates
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import com.contaxcell.app.domain.Valoracion
import java.io.InputStream
import java.io.OutputStream
import java.time.LocalDate
import java.time.ZoneId
import java.util.Date
import org.apache.poi.ss.usermodel.BorderStyle
import org.apache.poi.ss.usermodel.Cell
import org.apache.poi.ss.usermodel.CellStyle
import org.apache.poi.ss.usermodel.CellType
import org.apache.poi.ss.usermodel.DateUtil
import org.apache.poi.ss.usermodel.FillPatternType
import org.apache.poi.ss.usermodel.HorizontalAlignment
import org.apache.poi.ss.usermodel.IndexedColors
import org.apache.poi.ss.usermodel.Sheet
import org.apache.poi.ss.usermodel.Workbook
import org.apache.poi.xssf.usermodel.XSSFWorkbook

class ExcelImportException(message: String, cause: Throwable? = null) : Exception(message, cause)

data class ExcelImportResult(
    val book: Libro,
    val warnings: List<String>,
)

data class ExcelExportResult(val warnings: List<String> = emptyList())

/**
 * Reads and writes the same cell layout as the desktop template. The Android export is
 * self-contained, formula-enabled, and can be imported again by either app.
 */
class ExcelBookService {
    fun import(input: InputStream): ExcelImportResult {
        val workbook = try {
            XSSFWorkbook(input)
        } catch (error: Exception) {
            throw ExcelImportException(
                "No se ha podido abrir el archivo. Comprueba que sea un .xlsx válido.",
                error,
            )
        }
        workbook.use {
            val movementsSheet = workbook.getSheet(MOVEMENTS_SHEET)
                ?: throw ExcelImportException(
                    "El archivo no tiene una hoja llamada «Movimientos». ¿Seguro que es la contabilidad?",
                )
            val warnings = mutableListOf<String>()
            val categories = readCategories(movementsSheet).toMutableList()
            val movements = readMovements(movementsSheet)
            val known = categories.mapTo(mutableSetOf()) { it.nombre }
            movements.map { it.categoria }.filter(String::isNotBlank).forEach { name ->
                if (known.add(name)) {
                    categories += Categoria(name)
                    warnings += "La categoría «$name» no estaba en el panel; se ha añadido como gasto."
                }
            }
            var book = Libro(
                ajustes = Ajustes(saldoInicial = number(movementsSheet.row(2)?.cell(10))),
                categorias = categories.ifEmpty { Libro.empty().categorias },
                movimientos = movements,
            )
            workbook.getSheet(BUDGET_SHEET)?.let { book = readBudget(it, book) }
            workbook.getSheet(INVESTMENTS_SHEET)?.let { book = readInvestments(it, book) }
            if (book.movimientos.isEmpty()) {
                warnings += "No se ha encontrado ningún movimiento con fecha e importe. Revisa las columnas A, E y F."
            }
            return ExcelImportResult(book.normalized(), warnings)
        }
    }

    fun export(output: OutputStream, book: Libro, year: Int): ExcelExportResult {
        val normalized = book.normalized()
        val warnings = if (normalized.categorias.count { it.tipo == ContaXcellValues.INVERSION } > 1) {
            listOf("La plantilla solo contempla una categoría principal de tipo Inversión.")
        } else emptyList()
        XSSFWorkbook().use { workbook ->
            val styles = Styles(workbook)
            writeMovements(workbook.createSheet(MOVEMENTS_SHEET), normalized, year, styles)
            writeSummary(workbook.createSheet(SUMMARY_SHEET), normalized, year, styles)
            writeBudget(workbook.createSheet(BUDGET_SHEET), normalized, styles)
            writeInvestments(workbook.createSheet(INVESTMENTS_SHEET), normalized, styles)
            workbook.creationHelper.createFormulaEvaluator().evaluateAll()
            workbook.write(output)
        }
        return ExcelExportResult(warnings)
    }

    private fun readCategories(sheet: Sheet): List<Categoria> {
        val categories = mutableListOf<Categoria>()
        for (rowNumber in 5 until 39) {
            val row = sheet.row(rowNumber)
            val name = text(row?.cell(9))
            if (name.isBlank() || name.uppercase().startsWith("TOTAL")) break
            val rawType = text(row?.cell(10)).lowercase()
            val type = when {
                "ingreso" in rawType -> ContaXcellValues.INGRESO
                "inversi" in rawType -> ContaXcellValues.INVERSION
                else -> ContaXcellValues.GASTO
            }
            categories += Categoria(name, type)
        }
        return categories
    }

    private fun readMovements(sheet: Sheet): List<Movimiento> {
        val result = mutableListOf<Movimiento>()
        val last = minOf(sheet.lastRowNum, MAX_ROWS - 1)
        for (rowNumber in 1..last) {
            val row = sheet.row(rowNumber) ?: continue
            val date = date(row.cell(0))
            if (date.isBlank()) continue
            val income = number(row.cell(4))
            val expense = number(row.cell(5))
            val amount = kotlin.math.abs(if (income != 0.0) income else expense)
            if (amount == 0.0) continue
            result += Movimiento(
                fecha = date,
                descripcion = text(row.cell(2)),
                categoria = text(row.cell(3)),
                importe = amount,
                activo = text(row.cell(7)),
            )
        }
        return result
    }

    private fun readBudget(sheet: Sheet, book: Libro): Libro {
        val header = findRow(sheet, 0, "CATEGOR").takeIf { it >= 0 } ?: 3
        val expenses = book.categorias.filter { it.tipo == ContaXcellValues.GASTO }
        val budgets = mutableMapOf<String, Double>()
        var emptyCount = 0
        for ((index, rowNumber) in ((header + 1)..minOf(sheet.lastRowNum, header + MAX_BLOCK)).withIndex()) {
            val row = sheet.row(rowNumber)
            val name = text(row?.cell(0))
            if (name.uppercase().startsWith("TOTAL")) break
            if (name.isBlank() && row?.cell(1) == null) {
                emptyCount++
                if (emptyCount >= 3) break
            } else emptyCount = 0
            val category = book.categoria(name) ?: expenses.getOrNull(index)
            category?.let { budgets[it.nombre] = number(row?.cell(1)) }
        }
        val targetRow = findRow(sheet, 0, "OBJETIVO DE INVERSI")
        val target = if (targetRow >= 0) number(sheet.row(targetRow)?.cell(1)) else book.ajustes.objetivoInversion
        return book.copy(
            ajustes = book.ajustes.copy(objetivoInversion = target),
            categorias = book.categorias.map { it.copy(presupuesto = budgets[it.nombre] ?: it.presupuesto) },
        )
    }

    private fun readInvestments(sheet: Sheet, book: Libro): Libro {
        val assetHeader = findRow(sheet, 0, "ACTIVO").takeIf { it >= 0 } ?: 4
        val assets = mutableListOf<Activo>()
        for (rowNumber in assetHeader + 1..minOf(sheet.lastRowNum, assetHeader + MAX_BLOCK)) {
            val row = sheet.row(rowNumber)
            val name = text(row?.cell(0))
            if (name.isBlank() || name.uppercase().startsWith("TOTAL")) break
            assets += Activo(
                nombre = name,
                aportacionInicial = number(row?.cell(1)),
                valorMercado = number(row?.cell(5)),
                ultimaValoracion = date(row?.cell(8)),
            )
        }

        val freeEntries = mutableListOf<AportacionGratis>()
        val freeHeader = (0..minOf(sheet.lastRowNum, 199)).firstOrNull { rowNumber ->
            text(sheet.row(rowNumber)?.cell(0)).uppercase() == "FECHA" &&
                text(sheet.row(rowNumber)?.cell(1)).uppercase().startsWith("ACTIVO")
        }
        if (freeHeader != null) {
            for (rowNumber in freeHeader + 1..minOf(sheet.lastRowNum, freeHeader + MAX_BLOCK)) {
                val row = sheet.row(rowNumber)
                val entryDate = date(row?.cell(0))
                if (text(row?.cell(0)).uppercase().startsWith("TOTAL")) break
                val amount = number(row?.cell(3))
                if (entryDate.isNotBlank() && amount != 0.0) {
                    freeEntries += AportacionGratis(
                        fecha = entryDate,
                        activo = text(row?.cell(1)),
                        concepto = text(row?.cell(2)),
                        importe = amount,
                    )
                }
            }
        }

        val history = mutableListOf<Valoracion>()
        val historyHeader = findRow(sheet, 10, "FECHA").takeIf { it >= 0 } ?: 4
        for (rowNumber in historyHeader + 1..minOf(sheet.lastRowNum, historyHeader + MAX_BLOCK)) {
            val entryDate = date(sheet.row(rowNumber)?.cell(10))
            if (entryDate.isNotBlank()) {
                history += Valoracion(entryDate, number(sheet.row(rowNumber)?.cell(12)))
            }
        }
        return book.copy(activos = assets, aportacionesGratis = freeEntries, historico = history)
    }

    private fun writeMovements(sheet: Sheet, book: Libro, year: Int, styles: Styles) {
        val headers = listOf("Fecha", "Mes", "Descripción", "Categoría", "Ingreso", "Gasto", "Balance", "Activo")
        writeHeader(sheet, 0, 0, headers, styles.header)
        val sorted = book.movimientos.sortedBy { it.fecha }
        sorted.forEachIndexed { index, movement ->
            val rowNumber = index + 1
            val row = sheet.requiredRow(rowNumber)
            row.requiredCell(0).setCellValue(asDate(movement.fecha))
            row.requiredCell(0).cellStyle = styles.date
            row.requiredCell(1).cellFormula = "IF(A${rowNumber + 1}=\"\",\"\",TEXT(A${rowNumber + 1},\"mmmm yyyy\"))"
            row.requiredCell(2).setCellValue(movement.descripcion)
            row.requiredCell(3).setCellValue(movement.categoria)
            val income = book.tipoDe(movement.categoria) == ContaXcellValues.INGRESO
            if (income) row.requiredCell(4).setCellValue(movement.importe)
            else row.requiredCell(5).setCellValue(movement.importe)
            row.requiredCell(4).cellStyle = styles.money
            row.requiredCell(5).cellStyle = styles.money
            row.requiredCell(6).cellFormula =
                "K3+SUM(E\$2:E${rowNumber + 1})-SUM(F\$2:F${rowNumber + 1})"
            row.requiredCell(6).cellStyle = styles.money
            row.requiredCell(7).setCellValue(movement.activo)
        }
        writeHeader(sheet, 0, 9, listOf("Categoría", "Tipo", "Mes", "Año", "Media"), styles.header)
        val activeMonth = sorted.lastOrNull { IsoDates.yearOf(it.fecha) == year }?.fecha?.take(7)?.plus("-01")
            ?: "$year-12-01"
        sheet.requiredRow(1).requiredCell(10).setCellValue(asDate(activeMonth))
        sheet.requiredRow(1).requiredCell(10).cellStyle = styles.date
        sheet.requiredRow(2).requiredCell(10).setCellValue(book.ajustes.saldoInicial)
        sheet.requiredRow(2).requiredCell(10).cellStyle = styles.money
        book.categorias.forEachIndexed { index, category ->
            val rowNumber = index + 5
            val row = sheet.requiredRow(rowNumber)
            row.requiredCell(9).setCellValue(category.nombre)
            row.requiredCell(10).setCellValue(category.tipo)
        }
        setWidths(sheet, listOf(12, 16, 34, 24, 14, 14, 14, 20, 3, 25, 14, 14, 14, 14))
        sheet.createFreezePane(0, 1)
        if (sorted.isNotEmpty()) sheet.setAutoFilter(org.apache.poi.ss.util.CellRangeAddress(0, sorted.size, 0, 7))
    }

    private fun writeSummary(sheet: Sheet, book: Libro, year: Int, styles: Styles) {
        sheet.requiredRow(0).requiredCell(0).setCellValue("Resumen $year")
        sheet.requiredRow(0).requiredCell(0).cellStyle = styles.title
        writeHeader(sheet, 2, 0, listOf("Mes", "Ingresos", "Gastos", "Ahorro", "Inversión", "Saldo"), styles.header)
        var balance = book.ajustes.saldoInicial
        (1..12).forEach { month ->
            val key = "%04d-%02d".format(year, month)
            val entries = book.movimientos.filter { it.fecha.startsWith(key) }
            val income = entries.filter { book.tipoDe(it.categoria) == ContaXcellValues.INGRESO }.sumOf { it.importe }
            val expense = entries.filter { book.tipoDe(it.categoria) == ContaXcellValues.GASTO }.sumOf { it.importe }
            val investment = entries.filter { book.tipoDe(it.categoria) == ContaXcellValues.INVERSION }.sumOf { it.importe }
            balance += income - expense - investment
            val row = sheet.requiredRow(month + 2)
            row.requiredCell(0).setCellValue(ContaXcellValues.MESES[month - 1])
            listOf(income, expense, income - expense, investment, balance).forEachIndexed { index, value ->
                row.requiredCell(index + 1).setCellValue(DomainNumbers.money(value))
                row.requiredCell(index + 1).cellStyle = styles.money
            }
        }
        setWidths(sheet, listOf(18, 16, 16, 16, 16, 16))
    }

    private fun writeBudget(sheet: Sheet, book: Libro, styles: Styles) {
        sheet.requiredRow(0).requiredCell(0).setCellValue("Presupuesto mensual")
        sheet.requiredRow(0).requiredCell(0).cellStyle = styles.title
        writeHeader(sheet, 3, 0, listOf("Categoría", "Presupuesto", "Real", "Disponible", "% usado"), styles.header)
        book.categorias.filter { it.tipo == ContaXcellValues.GASTO }.forEachIndexed { index, category ->
            val row = sheet.requiredRow(index + 4)
            row.requiredCell(0).setCellValue(category.nombre)
            row.requiredCell(1).setCellValue(category.presupuesto)
            row.requiredCell(1).cellStyle = styles.money
        }
        val targetRow = book.categorias.count { it.tipo == ContaXcellValues.GASTO } + 7
        sheet.requiredRow(targetRow).requiredCell(0).setCellValue("OBJETIVO DE INVERSIÓN")
        sheet.row(targetRow).requiredCell(1).setCellValue(book.ajustes.objetivoInversion)
        sheet.requiredRow(targetRow).requiredCell(1).cellStyle = styles.money
        setWidths(sheet, listOf(30, 16, 16, 16, 14))
    }

    private fun writeInvestments(sheet: Sheet, book: Libro, styles: Styles) {
        sheet.requiredRow(0).requiredCell(0).setCellValue("Inversiones")
        sheet.requiredRow(0).requiredCell(0).cellStyle = styles.title
        writeHeader(
            sheet,
            4,
            0,
            listOf("ACTIVO", "Aportación inicial", "Aportado", "Gratis", "Total", "Valor mercado", "Generado", "Rentabilidad", "Última valoración"),
            styles.header,
        )
        book.activos.forEachIndexed { index, asset ->
            val row = sheet.requiredRow(index + 5)
            row.requiredCell(0).setCellValue(asset.nombre)
            row.requiredCell(1).setCellValue(asset.aportacionInicial)
            row.requiredCell(5).setCellValue(asset.valorMercado)
            row.requiredCell(8).apply {
                if (asset.ultimaValoracion.isNotBlank()) setCellValue(asDate(asset.ultimaValoracion))
                cellStyle = styles.date
            }
            row.requiredCell(1).cellStyle = styles.money
            row.requiredCell(5).cellStyle = styles.money
        }
        val freeHeader = maxOf(35, book.activos.size + 8)
        writeHeader(sheet, freeHeader, 0, listOf("FECHA", "ACTIVO", "Concepto", "Importe", "Títulos"), styles.header)
        book.aportacionesGratis.forEachIndexed { index, entry ->
            val row = sheet.requiredRow(freeHeader + index + 1)
            row.requiredCell(0).setCellValue(asDate(entry.fecha))
            row.requiredCell(0).cellStyle = styles.date
            row.requiredCell(1).setCellValue(entry.activo)
            row.requiredCell(2).setCellValue(entry.concepto)
            row.requiredCell(3).setCellValue(entry.importe)
            row.requiredCell(3).cellStyle = styles.money
            row.requiredCell(4).setCellValue(entry.titulos)
            row.requiredCell(4).cellStyle = styles.titles
        }
        writeHeader(sheet, 4, 10, listOf("FECHA", "Aportado", "Valor mercado", "Generado"), styles.header)
        book.historico.forEachIndexed { index, value ->
            val row = sheet.requiredRow(index + 5)
            row.requiredCell(10).setCellValue(asDate(value.fecha))
            row.requiredCell(10).cellStyle = styles.date
            row.requiredCell(12).setCellValue(value.valorMercado)
            row.requiredCell(12).cellStyle = styles.money
        }
        setWidths(sheet, listOf(25, 17, 17, 17, 17, 17, 17, 15, 18, 3, 14, 17, 17, 17))
    }

    private fun writeHeader(sheet: Sheet, rowNumber: Int, column: Int, labels: List<String>, style: CellStyle) {
        val row = sheet.requiredRow(rowNumber)
        labels.forEachIndexed { index, label ->
            row.requiredCell(column + index).apply {
                setCellValue(label)
                cellStyle = style
            }
        }
    }

    private fun findRow(sheet: Sheet, column: Int, prefix: String): Int {
        val target = prefix.uppercase()
        for (rowNumber in 0..minOf(sheet.lastRowNum, 119)) {
            if (text(sheet.row(rowNumber)?.cell(column)).uppercase().startsWith(target)) return rowNumber
        }
        return -1
    }

    private fun text(cell: Cell?): String {
        if (cell == null) return ""
        return when (effectiveType(cell)) {
            CellType.STRING -> cell.stringCellValue.trim()
            CellType.NUMERIC -> if (DateUtil.isCellDateFormatted(cell)) date(cell) else {
                val value = cell.numericCellValue
                if (value % 1.0 == 0.0) value.toLong().toString() else value.toString()
            }
            CellType.BOOLEAN -> cell.booleanCellValue.toString()
            else -> ""
        }
    }

    private fun number(cell: Cell?): Double {
        if (cell == null) return 0.0
        if (effectiveType(cell) == CellType.NUMERIC) return DomainNumbers.money(cell.numericCellValue)
        val cleaned = text(cell).filter { it.isDigit() || it in ",.-" }.replace(',', '.')
        return cleaned.toDoubleOrNull()?.let(DomainNumbers::money) ?: 0.0
    }

    private fun date(cell: Cell?): String {
        if (cell == null) return ""
        if (effectiveType(cell) == CellType.NUMERIC && DateUtil.isValidExcelDate(cell.numericCellValue)) {
            val local = DateUtil.getLocalDateTime(cell.numericCellValue).toLocalDate()
            return local.toString()
        }
        val value = textWithoutDateRecursion(cell).trim()
        value.take(10).takeIf(IsoDates::isValid)?.let { return it }
        listOf('/', '-', '.').forEach { separator ->
            val parts = value.split(separator)
            if (parts.size == 3 && parts.all { it.trim().toIntOrNull() != null }) {
                val day = parts[0].trim().toInt()
                val month = parts[1].trim().toInt()
                var year = parts[2].trim().toInt()
                if (year < 100) year += 2000
                runCatching { LocalDate.of(year, month, day).toString() }.getOrNull()?.let { return it }
            }
        }
        return ""
    }

    private fun textWithoutDateRecursion(cell: Cell): String = when (effectiveType(cell)) {
        CellType.STRING -> cell.stringCellValue
        CellType.NUMERIC -> cell.numericCellValue.toString()
        else -> ""
    }

    private fun effectiveType(cell: Cell): CellType =
        if (cell.cellType == CellType.FORMULA) cell.cachedFormulaResultType else cell.cellType

    private fun asDate(value: String): Date = LocalDate.parse(value).atStartOfDay(ZoneId.systemDefault()).toInstant().let(Date::from)

    private fun setWidths(sheet: Sheet, widths: List<Int>) {
        widths.forEachIndexed { index, width -> sheet.setColumnWidth(index, width * 256) }
    }

    private fun Sheet.row(index: Int) = getRow(index)
    private fun Sheet.requiredRow(index: Int) = getRow(index) ?: createRow(index)
    private fun org.apache.poi.ss.usermodel.Row.cell(index: Int) = getCell(index)
    private fun org.apache.poi.ss.usermodel.Row.requiredCell(index: Int) = getCell(index) ?: createCell(index)

    private class Styles(workbook: Workbook) {
        val header = workbook.createCellStyle().apply {
            fillForegroundColor = IndexedColors.DARK_TEAL.index
            fillPattern = FillPatternType.SOLID_FOREGROUND
            alignment = HorizontalAlignment.CENTER
            setFont(workbook.createFont().apply {
                color = IndexedColors.WHITE.index
                bold = true
            })
            borderBottom = BorderStyle.THIN
        }
        val title = workbook.createCellStyle().apply {
            setFont(workbook.createFont().apply { bold = true; fontHeightInPoints = 16 })
        }
        val money = workbook.createCellStyle().apply { dataFormat = workbook.createDataFormat().getFormat("#,##0.00 [$€-es-ES]") }
        val titles = workbook.createCellStyle().apply { dataFormat = workbook.createDataFormat().getFormat("0.000000") }
        val date = workbook.createCellStyle().apply { dataFormat = workbook.createDataFormat().getFormat("dd/mm/yyyy") }
    }

    private companion object {
        const val MOVEMENTS_SHEET = "Movimientos"
        const val SUMMARY_SHEET = "Resumen"
        const val BUDGET_SHEET = "Presupuesto"
        const val INVESTMENTS_SHEET = "Inversiones"
        const val MAX_ROWS = 20_000
        const val MAX_BLOCK = 500
    }
}
