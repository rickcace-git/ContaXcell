package com.contaxcell.app.domain

import java.math.BigDecimal
import java.math.RoundingMode

object SpanishFormat {
    const val HIDDEN = "••••"

    fun number(value: Double, decimals: Int = 2): String {
        if (!value.isFinite()) return "—"
        val absolute = BigDecimal.valueOf(kotlin.math.abs(value)).setScale(decimals, RoundingMode.HALF_UP).toPlainString()
        val split = absolute.split('.')
        val integer = split[0].reversed().chunked(3).joinToString(".").reversed()
        val sign = if (value < 0) "-" else ""
        return if (decimals > 0) "$sign$integer,${split.getOrElse(1) { "" }.padEnd(decimals, '0')}" else "$sign$integer"
    }

    fun euros(value: Double, hidden: Boolean = false, alwaysVisible: Boolean = false): String =
        if (hidden && !alwaysVisible) HIDDEN else "${number(value)} €"

    fun signedEuros(value: Double, hidden: Boolean = false, alwaysVisible: Boolean = false): String {
        if (hidden && !alwaysVisible) return HIDDEN
        return (if (value > 0) "+" else "") + number(value) + " €"
    }

    fun percentage(value: Double, decimals: Int = 1): String =
        if (!value.isFinite()) "—" else "${number(value * 100, decimals)} %"

    fun decimal(value: Double, decimals: Int = 1): String = number(value, decimals)

    /** Accepts Spanish/English decimal separators, grouping dots, spaces and the euro symbol. */
    fun parseNumber(text: String?): Double? {
        var clean = text?.trim()?.replace("€", "")?.replace(" ", "")?.replace("\u00a0", "") ?: return null
        if (clean.isEmpty()) return null
        clean = when {
            ',' in clean -> clean.replace(".", "").replace(',', '.')
            clean.count { it == '.' } > 1 -> clean.replace(".", "")
            else -> clean
        }
        return clean.toDoubleOrNull()
    }

    fun shortDate(iso: String): String {
        if (!IsoDates.isValid(iso)) return ""
        val (year, month, day) = iso.split('-')
        return "${day.toInt()} ${ContaXcellValues.MESES_CORTOS[month.toInt() - 1]} $year"
    }

    fun longDate(iso: String): String {
        if (!IsoDates.isValid(iso)) return ""
        val (year, month, day) = iso.split('-')
        return "${day.toInt()} de ${ContaXcellValues.MESES[month.toInt() - 1]} de $year"
    }

    fun dateToText(iso: String): String {
        if (!IsoDates.isValid(iso)) return ""
        val (year, month, day) = iso.split('-')
        return "$day/$month/$year"
    }

    /** Accepts d/M/yy, d-M-yyyy, d.M.yyyy and ISO yyyy-MM-dd. */
    fun parseDate(text: String?): String? {
        val clean = text?.trim().orEmpty()
        if (clean.isEmpty()) return null
        if (IsoDates.isValid(clean)) return clean
        val separator = listOf('/', '-', '.').firstOrNull(clean::contains) ?: return null
        val parts = clean.split(separator).map(String::trim)
        if (parts.size != 3 || parts.any { it.toIntOrNull() == null }) return null
        val first = parts[0].toInt()
        val second = parts[1].toInt()
        val third = parts[2].toInt()
        val (year, month, day) = if (first > 31) Triple(first, second, third) else Triple(if (third < 100) third + 2000 else third, second, first)
        return IsoDates.fromParts(year, month, day)
    }
}
