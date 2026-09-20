package com.contaxcell.app.domain

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.math.BigDecimal
import java.math.RoundingMode
import java.util.Calendar
import java.util.Locale
import kotlin.random.Random

object ContaXcellValues {
    const val INGRESO = "Ingreso"
    const val GASTO = "Gasto"
    const val INVERSION = "Inversión"
    val TIPOS = setOf(INGRESO, GASTO, INVERSION)

    const val SEMANAL = "Semanal"
    const val QUINCENAL = "Quincenal"
    const val MENSUAL = "Mensual"
    const val BIMESTRAL = "Bimestral"
    const val TRIMESTRAL = "Trimestral"
    const val SEMESTRAL = "Semestral"
    const val ANUAL = "Anual"
    val PERIODOS = setOf(SEMANAL, QUINCENAL, MENSUAL, BIMESTRAL, TRIMESTRAL, SEMESTRAL, ANUAL)

    val PASO = mapOf(
        SEMANAL to (7 to 0), QUINCENAL to (14 to 0), MENSUAL to (0 to 1),
        BIMESTRAL to (0 to 2), TRIMESTRAL to (0 to 3), SEMESTRAL to (0 to 6),
        ANUAL to (0 to 12),
    )
    val VECES_AL_ANIO = mapOf(
        SEMANAL to 52, QUINCENAL to 26, MENSUAL to 12, BIMESTRAL to 6,
        TRIMESTRAL to 4, SEMESTRAL to 2, ANUAL to 1,
    )

    const val ME_DEBEN = "Me deben"
    const val DEBO = "Debo"
    val SENTIDOS = setOf(ME_DEBEN, DEBO)

    val TEMAS = setOf("auto", "claro", "oscuro")
    val MESES = listOf(
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    val MESES_CORTOS = listOf("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    val DIAS_CORTOS = listOf("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
    val CATEGORIAS_ACTIVO = listOf("Indexados", "Acciones sueltas", "Cripto", "Bonos", "Oro")
}

object DomainNumbers {
    fun money(value: Double): Double = rounded(value, 2)
    fun titles(value: Double): Double = rounded(value, 6)

    private fun rounded(value: Double, scale: Int): Double {
        if (!value.isFinite()) return 0.0
        return BigDecimal.valueOf(value).setScale(scale, RoundingMode.HALF_UP).toDouble()
    }
}

object IsoDates {
    private val iso = Regex("^(\\d{4})-(\\d{2})-(\\d{2})$")

    fun isValid(value: String?): Boolean {
        val match = iso.matchEntire(value.orEmpty()) ?: return false
        val (year, month, day) = match.destructured
        return calendar(year.toInt(), month.toInt(), day.toInt()) != null
    }

    fun today(): String {
        val now = Calendar.getInstance()
        return "%04d-%02d-%02d".format(
            Locale.ROOT,
            now.get(Calendar.YEAR),
            now.get(Calendar.MONTH) + 1,
            now.get(Calendar.DAY_OF_MONTH),
        )
    }

    fun monthOf(value: String): String = if (isValid(value)) value.take(7) else ""
    fun yearOf(value: String): Int = if (isValid(value)) value.take(4).toInt() else 0
    fun monthKey(year: Int, zeroBasedMonth: Int): String = "%04d-%02d".format(Locale.ROOT, year, zeroBasedMonth + 1)

    fun monthName(key: String, short: Boolean = false): String {
        val parts = key.split("-")
        val index = parts.getOrNull(1)?.toIntOrNull()?.minus(1) ?: return key
        if (index !in 0..11) return key
        val names = if (short) ContaXcellValues.MESES_CORTOS else ContaXcellValues.MESES
        return "${names[index]} ${parts.firstOrNull().orEmpty()}"
    }

    fun daysOfMonth(key: String): List<String> {
        val parts = key.split('-')
        if (parts.size != 2) return emptyList()
        val year = parts[0].toIntOrNull() ?: return emptyList()
        val month = parts[1].toIntOrNull() ?: return emptyList()
        if (year !in 1..9999 || month !in 1..12) return emptyList()
        val probe = calendar(year, month, 1) ?: return emptyList()
        return (1..probe.getActualMaximum(Calendar.DAY_OF_MONTH)).map { day ->
            "%04d-%02d-%02d".format(Locale.ROOT, year, month, day)
        }
    }

    fun weekday(value: String): String {
        val parsed = parse(value) ?: return ""
        // Calendar starts on Sunday; desktop/Python starts on Monday.
        val mondayIndex = (parsed.get(Calendar.DAY_OF_WEEK) + 5) % 7
        return ContaXcellValues.DIAS_CORTOS[mondayIndex]
    }

    fun plusDays(value: String, days: Int): String {
        val parsed = parse(value) ?: return ""
        parsed.add(Calendar.DAY_OF_MONTH, days)
        return format(parsed)
    }

    /** Adds from the original day, clamping to the target month's final day. */
    fun plusMonths(value: String, months: Int): String {
        val match = iso.matchEntire(value) ?: return ""
        val (yearText, monthText, dayText) = match.destructured
        if (!isValid(value)) return ""
        val total = yearText.toInt().toLong() * 12L + monthText.toInt() - 1L + months
        val newYear = Math.floorDiv(total, 12L).toInt()
        val newMonth0 = Math.floorMod(total, 12L).toInt()
        if (newYear !in 1..9999) return ""
        val probe = Calendar.getInstance().apply {
            clear()
            isLenient = false
            set(Calendar.YEAR, newYear)
            set(Calendar.MONTH, newMonth0)
            set(Calendar.DAY_OF_MONTH, 1)
        }
        val day = minOf(dayText.toInt(), probe.getActualMaximum(Calendar.DAY_OF_MONTH))
        return "%04d-%02d-%02d".format(Locale.ROOT, newYear, newMonth0 + 1, day)
    }

    internal fun fromParts(year: Int, month: Int, day: Int): String? =
        calendar(year, month, day)?.let(::format)

    private fun parse(value: String): Calendar? {
        val match = iso.matchEntire(value) ?: return null
        val (year, month, day) = match.destructured
        return calendar(year.toInt(), month.toInt(), day.toInt())
    }

    private fun calendar(year: Int, month: Int, day: Int): Calendar? = runCatching {
        Calendar.getInstance().apply {
            clear()
            isLenient = false
            set(year, month - 1, day)
            timeInMillis // Force strict validation.
        }
    }.getOrNull()

    private fun format(calendar: Calendar): String = "%04d-%02d-%02d".format(
        Locale.ROOT,
        calendar.get(Calendar.YEAR),
        calendar.get(Calendar.MONTH) + 1,
        calendar.get(Calendar.DAY_OF_MONTH),
    )
}

private val idAlphabet = ('a'..'z') + ('0'..'9')
fun newId(): String = buildString(10) { repeat(10) { append(idAlphabet[Random.nextInt(idAlphabet.size)]) } }

@Serializable
data class Categoria(
    val nombre: String,
    val tipo: String = ContaXcellValues.GASTO,
    val presupuesto: Double = 0.0,
) {
    fun normalized() = copy(
        nombre = nombre.trim(),
        tipo = tipo.takeIf(ContaXcellValues.TIPOS::contains) ?: ContaXcellValues.GASTO,
        presupuesto = DomainNumbers.money(presupuesto),
    )
}

@Serializable
data class Activo(
    val nombre: String,
    @SerialName("aportacion_inicial") val aportacionInicial: Double = 0.0,
    @SerialName("valor_mercado") val valorMercado: Double = 0.0,
    @SerialName("ultima_valoracion") val ultimaValoracion: String = "",
    val categoria: String = "",
    val isin: String = "",
    val simbolo: String = "",
) {
    fun normalized() = copy(
        nombre = nombre.trim(),
        aportacionInicial = DomainNumbers.money(aportacionInicial),
        valorMercado = DomainNumbers.money(valorMercado),
        ultimaValoracion = ultimaValoracion.takeIf(IsoDates::isValid).orEmpty(),
        categoria = categoria.trim(),
        isin = isin.trim().uppercase(Locale.ROOT),
        simbolo = simbolo.trim().uppercase(Locale.ROOT),
    )
}

@Serializable
data class Movimiento(
    val fecha: String,
    val descripcion: String = "",
    val categoria: String = "",
    val importe: Double = 0.0,
    val activo: String = "",
    val origen: String = "",
    val titulos: Double = 0.0,
    val id: String = newId(),
) {
    fun normalized() = copy(
        descripcion = descripcion.trim(), categoria = categoria.trim(),
        importe = kotlin.math.abs(DomainNumbers.money(importe)), activo = activo.trim(),
        origen = origen.trim(), titulos = DomainNumbers.titles(titulos),
        id = id.trim().ifEmpty(::newId),
    )
}

@Serializable
data class AportacionGratis(
    val fecha: String,
    val activo: String = "",
    val concepto: String = "",
    val importe: Double = 0.0,
    val titulos: Double = 0.0,
    val id: String = newId(),
) {
    fun normalized() = copy(
        activo = activo.trim(), concepto = concepto.trim(),
        importe = DomainNumbers.money(importe), titulos = DomainNumbers.titles(titulos),
        id = id.trim().ifEmpty(::newId),
    )
}

@Serializable
data class Cotizacion(
    val simbolo: String,
    val fecha: String,
    val precio: Double = 0.0,
    val moneda: String = "EUR",
) {
    fun normalized() = copy(
        simbolo = simbolo.trim().uppercase(Locale.ROOT),
        fecha = fecha.takeIf(IsoDates::isValid).orEmpty(),
        precio = DomainNumbers.money(precio),
        moneda = moneda.trim().ifEmpty { "EUR" },
    )
}

@Serializable
data class Valoracion(
    val fecha: String,
    @SerialName("valor_mercado") val valorMercado: Double = 0.0,
    val id: String = newId(),
) {
    fun normalized() = copy(
        valorMercado = DomainNumbers.money(valorMercado),
        id = id.trim().ifEmpty(::newId),
    )
}

@Serializable
data class Periodico(
    val nombre: String,
    val categoria: String = "",
    val importe: Double = 0.0,
    val periodo: String = ContaXcellValues.MENSUAL,
    val desde: String = "",
    val hasta: String = "",
    val activo: String = "",
    val encendido: Boolean = true,
    @SerialName("apuntado_hasta") val apuntadoHasta: String = "",
    val id: String = newId(),
) {
    fun normalized(): Periodico {
        val cleanFrom = desde.takeIf(IsoDates::isValid).orEmpty()
        val cleanUntil = hasta.takeIf { IsoDates.isValid(it) && (cleanFrom.isEmpty() || it >= cleanFrom) }.orEmpty()
        return copy(
            nombre = nombre.trim(), categoria = categoria.trim(),
            importe = kotlin.math.abs(DomainNumbers.money(importe)),
            periodo = periodo.takeIf(ContaXcellValues.PERIODOS::contains) ?: ContaXcellValues.MENSUAL,
            desde = cleanFrom, hasta = cleanUntil, activo = activo.trim(),
            apuntadoHasta = apuntadoHasta.takeIf(IsoDates::isValid).orEmpty(),
            id = id.trim().ifEmpty(::newId),
        )
    }
}

@Serializable
data class Deuda(
    val quien: String,
    val sentido: String = ContaXcellValues.ME_DEBEN,
    val importe: Double = 0.0,
    val fecha: String = "",
    val concepto: String = "",
    val nota: String = "",
    val devuelto: Double = 0.0,
    val id: String = newId(),
) {
    fun normalized(): Deuda {
        val cleanAmount = kotlin.math.abs(DomainNumbers.money(importe))
        return copy(
            quien = quien.trim(),
            sentido = sentido.takeIf(ContaXcellValues.SENTIDOS::contains) ?: ContaXcellValues.ME_DEBEN,
            importe = cleanAmount,
            fecha = fecha.trim().takeIf(IsoDates::isValid).orEmpty(),
            concepto = concepto.trim(),
            nota = nota.trim(),
            devuelto = minOf(kotlin.math.abs(DomainNumbers.money(devuelto)), cleanAmount),
            id = id.trim().ifEmpty(::newId),
        )
    }
}

@Serializable
data class Ajustes(
    @SerialName("saldo_inicial") val saldoInicial: Double = 0.0,
    @SerialName("objetivo_inversion") val objetivoInversion: Double = 0.0,
    @SerialName("ocultar_importes") val ocultarImportes: Boolean = false,
    val tema: String = "auto",
    @SerialName("precios_al_dia") val preciosAlDia: String = "",
) {
    fun normalized() = copy(
        saldoInicial = DomainNumbers.money(saldoInicial),
        objetivoInversion = DomainNumbers.money(objetivoInversion),
        tema = tema.takeIf(ContaXcellValues.TEMAS::contains) ?: "auto",
        preciosAlDia = preciosAlDia.takeIf(IsoDates::isValid).orEmpty(),
    )
}

@Serializable
data class Libro(
    val version: Int = 1,
    val ajustes: Ajustes = Ajustes(),
    val categorias: List<Categoria> = emptyList(),
    val activos: List<Activo> = emptyList(),
    val movimientos: List<Movimiento> = emptyList(),
    @SerialName("aportaciones_gratis") val aportacionesGratis: List<AportacionGratis> = emptyList(),
    val historico: List<Valoracion> = emptyList(),
    val periodicos: List<Periodico> = emptyList(),
    val cotizaciones: List<Cotizacion> = emptyList(),
    val deudas: List<Deuda> = emptyList(),
) {
    fun normalized(): Libro {
        val cleanCategories = categorias.map(Categoria::normalized).distinctFirstBy { it.nombre }.ifEmpty { initialCategories() }
        return copy(
            version = 1,
            ajustes = ajustes.normalized(),
            categorias = cleanCategories,
            activos = activos.map(Activo::normalized).distinctFirstBy { it.nombre },
            movimientos = movimientos.map(Movimiento::normalized).filter { IsoDates.isValid(it.fecha) },
            aportacionesGratis = aportacionesGratis.map(AportacionGratis::normalized).filter { IsoDates.isValid(it.fecha) },
            historico = historico.map(Valoracion::normalized).filter { IsoDates.isValid(it.fecha) },
            periodicos = periodicos.map(Periodico::normalized).filter { it.nombre.isNotEmpty() && IsoDates.isValid(it.desde) },
            cotizaciones = cotizaciones.map(Cotizacion::normalized)
                .filter { it.simbolo.isNotEmpty() && it.fecha.isNotEmpty() && it.precio > 0 },
            deudas = deudas.map(Deuda::normalized).filter { it.quien.isNotEmpty() && IsoDates.isValid(it.fecha) },
        )
    }

    fun categoria(nombre: String): Categoria? = categorias.firstOrNull { it.nombre == nombre }
    fun tipoDe(nombreCategoria: String): String = categoria(nombreCategoria)?.tipo ?: ContaXcellValues.GASTO
    fun movimiento(id: String): Movimiento? = movimientos.firstOrNull { it.id == id }
    fun activo(nombre: String): Activo? = activos.firstOrNull { it.nombre == nombre }
    fun activoPorIsin(isin: String): Activo? {
        val code = isin.trim().uppercase(Locale.ROOT)
        return code.takeIf(String::isNotEmpty)?.let { activos.firstOrNull { asset -> asset.isin == it } }
    }
    fun periodico(id: String): Periodico? = periodicos.firstOrNull { it.id == id }
    fun deuda(id: String): Deuda? = deudas.firstOrNull { it.id == id }

    companion object {
        fun empty(): Libro = Libro(categorias = initialCategories())

        private fun initialCategories() = listOf(
            Categoria("Sueldo", ContaXcellValues.INGRESO),
            Categoria("Otros Ingresos", ContaXcellValues.INGRESO),
            Categoria("Productos Básicos", presupuesto = 150.0),
            Categoria("Vivienda y Suministros", presupuesto = 700.0),
            Categoria("Transporte", presupuesto = 40.0),
            Categoria("Ocio y Caprichos", presupuesto = 80.0),
            Categoria("Comer fuera", presupuesto = 100.0),
            Categoria("Otros Gastos", presupuesto = 50.0),
            Categoria("Inversión", ContaXcellValues.INVERSION),
        )
    }
}

private inline fun <T> Iterable<T>.distinctFirstBy(key: (T) -> String): List<T> {
    val seen = mutableSetOf<String>()
    return filter { key(it).isNotEmpty() && seen.add(key(it)) }
}
