package com.contaxcell.app.domain

import com.contaxcell.app.domain.ContaXcellValues.ANUAL
import com.contaxcell.app.domain.ContaXcellValues.GASTO
import com.contaxcell.app.domain.ContaXcellValues.INGRESO
import com.contaxcell.app.domain.ContaXcellValues.INVERSION

data class FilaLibro(val movimiento: Movimiento, val tipo: String, val balance: Double) {
    val id get() = movimiento.id
    val fecha get() = movimiento.fecha
    val descripcion get() = movimiento.descripcion
    val categoria get() = movimiento.categoria
    val importe get() = movimiento.importe
    val activo get() = movimiento.activo
}

data class Totales(
    val ingresos: Double = 0.0,
    val gastos: Double = 0.0,
    val inversion: Double = 0.0,
    val porCategoria: Map<String, Double> = emptyMap(),
) {
    val ahorro get() = DomainNumbers.money(ingresos - gastos)
    val flujoNeto get() = DomainNumbers.money(ahorro - inversion)
    val tasaAhorro get() = if (ingresos > 0) ahorro / ingresos else 0.0
    val hayDatos get() = ingresos != 0.0 || gastos != 0.0 || inversion != 0.0
}

data class Tramo(
    val clave: String,
    val nombre: String,
    val corto: String,
    val totales: Totales,
    val saldoFinal: Double,
) { val hayDatos get() = totales.hayDatos }

typealias MesDelAnio = Tramo

data class FilaReparto(val nombre: String, val importe: Double, val porcentaje: Double)
data class Reparto(val total: Double, val filas: List<FilaReparto>)
data class ResumenPeriodo(
    val desde: String,
    val hasta: String,
    val tramos: List<Tramo>,
    val total: Totales,
    val mesesConDatos: Int,
    val gasto: Reparto,
    val ingreso: Reparto,
    val particion: String = Calculos.POR_MESES,
) {
    /** Compatibility alias for the original Android annual-summary UI. */
    val meses get() = tramos
}

typealias ResumenAnual = ResumenPeriodo

data class FilaPresupuesto(val nombre: String, val presupuesto: Double, val real: Double) {
    val disponible get() = DomainNumbers.money(presupuesto - real)
    val consumido get() = if (presupuesto > 0) real / presupuesto else if (real > 0) Double.POSITIVE_INFINITY else 0.0
}

data class Presupuesto(
    val mes: String,
    val filas: List<FilaPresupuesto>,
    val ingresos: Double,
    val aportado: Double,
    val objetivoInversion: Double,
) {
    val presupuestado get() = DomainNumbers.money(filas.sumOf { it.presupuesto })
    val gastado get() = DomainNumbers.money(filas.sumOf { it.real })
    val disponible get() = DomainNumbers.money(presupuestado - gastado)
    val consumido get() = if (presupuestado > 0) gastado / presupuestado else 0.0
    val margen get() = DomainNumbers.money(ingresos - presupuestado)
    val pendiente get() = DomainNumbers.money(maxOf(0.0, objetivoInversion - aportado))
}

data class FilaActivo(
    val nombre: String,
    val aportacionInicial: Double,
    val aportadoBanco: Double,
    val aportadoGratis: Double,
    val valorMercado: Double,
    val ultimaValoracion: String,
    val categoria: String = "",
    val titulos: Double = 0.0,
    val sinValorar: Boolean = false,
    val simbolo: String = "",
    val cotizado: Boolean = false,
) {
    val precioHoy get() = if (titulos > 0) valorMercado / titulos else 0.0
    val hayTitulos get() = titulos > 0
    val totalAportado get() = DomainNumbers.money(aportacionInicial + aportadoBanco + aportadoGratis)
    val generado get() = DomainNumbers.money(valorMercado - totalAportado)
    val rentabilidad get() = if (totalAportado > 0) generado / totalAportado else 0.0
}

data class PuntoHistorico(val id: String, val fecha: String, val aportado: Double, val valorMercado: Double) {
    val generado get() = DomainNumbers.money(valorMercado - aportado)
    val rentabilidad get() = if (aportado > 0) generado / aportado else 0.0
}

data class Cartera(
    val activos: List<FilaActivo>,
    val historico: List<PuntoHistorico>,
    val sinAsignarBanco: Double,
    val sinAsignarGratis: Double,
) {
    val aportacionInicial get() = sum { it.aportacionInicial }
    val aportadoBanco get() = sum { it.aportadoBanco }
    val aportadoGratis get() = sum { it.aportadoGratis }
    val totalAportado get() = sum { it.totalAportado }
    val valorMercado get() = sum { it.valorMercado }
    val generado get() = DomainNumbers.money(valorMercado - totalAportado)
    val rentabilidad get() = if (totalAportado > 0) generado / totalAportado else 0.0
    val ganadoSinPoner get() = DomainNumbers.money(generado + aportadoGratis)
    val sinValorar get() = activos.filter { it.sinValorar }
    val aportadoSinValorar get() = DomainNumbers.money(sinValorar.sumOf { it.totalAportado })
    private inline fun sum(value: (FilaActivo) -> Double) = DomainNumbers.money(activos.sumOf(value))
}

data class Indicadores(
    val desde: String,
    val hasta: String,
    val saldoBanco: Double,
    val mesesConDatos: Int,
    val ahorroMedio: Double,
    val gastoMedio: Double,
    val tasaAhorro: Double,
    val tramoMayorGasto: String,
    val mayorGasto: Movimiento?,
    val mesesDeColchon: Double,
    val inversion: Double,
    val totalAportado: Double,
    val valorCartera: Double,
    val generadoMercado: Double,
    val patrimonio: Double,
) {
    val mesMayorGasto get() = tramoMayorGasto
    val inversionAnual get() = inversion
}

data class Pendiente(val periodico: Periodico, val fechas: List<String>)
data class ApuntePendientes(val libro: Libro, val creados: List<Movimiento>)
data class CreacionPeriodico(val movimiento: Movimiento, val periodico: Periodico)
data class ActualizacionCotizaciones(val libro: Libro, val nuevas: Int)

data class PagoDeuda(val deuda: Deuda, val apuntado: Double)
data class ResumenDeudas(
    val teDeben: Double = 0.0,
    val debes: Double = 0.0,
    val abiertas: Int = 0,
    val saldadas: Int = 0,
    val personas: Int = 0,
) { val neto get() = DomainNumbers.money(teDeben - debes) }

data class SaldoConPersona(
    val quien: String,
    val teDeben: Double = 0.0,
    val debes: Double = 0.0,
    val cuantas: Int = 0,
) { val neto get() = DomainNumbers.money(teDeben - debes) }

data class ResumenPeriodicos(
    val encendidos: Int = 0,
    val apagados: Int = 0,
    val terminados: Int = 0,
    val gasto: Double = 0.0,
    val ingreso: Double = 0.0,
    val inversion: Double = 0.0,
) { val total get() = encendidos + apagados + terminados }

data class Compra(
    val id: String,
    val fecha: String,
    val descripcion: String,
    val importe: Double,
    val titulos: Double,
    val precioHoy: Double,
    val quoteAtPurchase: Double? = null,
    val quoteToday: Double? = null,
) {
    val precioPagado get() = if (titulos > 0) importe / titulos else 0.0
    val valorHoy get() = DomainNumbers.money(titulos * precioHoy)
    val generado get() = DomainNumbers.money(valorHoy - importe)
    val rentabilidad get() = if (importe > 0) generado / importe else 0.0
    val quoteChange get() = if (quoteAtPurchase != null && quoteAtPurchase > 0 && quoteToday != null) {
        quoteToday / quoteAtPurchase - 1.0
    } else null
}

data class GrupoCartera(val categoria: String, val activos: List<FilaActivo>, val peso: Double = 0.0) {
    val totalAportado get() = DomainNumbers.money(activos.sumOf { it.totalAportado })
    val valorMercado get() = DomainNumbers.money(activos.sumOf { it.valorMercado })
    val generado get() = DomainNumbers.money(valorMercado - totalAportado)
    val rentabilidad get() = if (totalAportado > 0) generado / totalAportado else 0.0
}

object Calculos {
    const val TOPE_VENCIMIENTOS = 4_000
    const val SIN_CATEGORIA = "Sin categoría"
    const val POR_DIAS = "días"
    const val POR_MESES = "meses"
    const val POR_ANIOS = "años"

    fun efectoEnBanco(libro: Libro, movimiento: Movimiento): Double =
        if (libro.tipoDe(movimiento.categoria) == INGRESO) movimiento.importe else -movimiento.importe

    fun ordenados(movimientos: List<Movimiento>): List<Movimiento> =
        movimientos.sortedWith(compareBy(Movimiento::fecha, Movimiento::id))

    fun conBalance(libro: Libro): List<FilaLibro> {
        var balance = libro.ajustes.saldoInicial
        return ordenados(libro.movimientos).map { movimiento ->
            balance = DomainNumbers.money(balance + efectoEnBanco(libro, movimiento))
            FilaLibro(movimiento, libro.tipoDe(movimiento.categoria), balance)
        }
    }

    fun saldoBanco(libro: Libro): Double = libro.movimientos.fold(libro.ajustes.saldoInicial) { balance, movimiento ->
        DomainNumbers.money(balance + efectoEnBanco(libro, movimiento))
    }

    fun saldoHasta(libro: Libro, fechaTope: String): Double =
        libro.movimientos.filter { it.fecha <= fechaTope }.fold(libro.ajustes.saldoInicial) { balance, movimiento ->
            DomainNumbers.money(balance + efectoEnBanco(libro, movimiento))
        }

    fun totales(libro: Libro, filtro: (Movimiento) -> Boolean): Totales {
        var ingresos = 0.0
        var gastos = 0.0
        var inversion = 0.0
        val byCategory = linkedMapOf<String, Double>()
        libro.movimientos.filter(filtro).forEach { movimiento ->
            byCategory[movimiento.categoria] = DomainNumbers.money((byCategory[movimiento.categoria] ?: 0.0) + movimiento.importe)
            when (libro.tipoDe(movimiento.categoria)) {
                INGRESO -> ingresos = DomainNumbers.money(ingresos + movimiento.importe)
                INVERSION -> inversion = DomainNumbers.money(inversion + movimiento.importe)
                else -> gastos = DomainNumbers.money(gastos + movimiento.importe)
            }
        }
        return Totales(ingresos, gastos, inversion, byCategory.toMap())
    }

    fun totalesDelMes(libro: Libro, mes: String) = totales(libro) { IsoDates.monthOf(it.fecha) == mes }
    fun totalesDelAnio(libro: Libro, anio: Int) = totales(libro) { IsoDates.yearOf(it.fecha) == anio }

    fun mesesEntre(desde: String, hasta: String): List<String> {
        if (!isMonthKey(desde) || !isMonthKey(hasta) || hasta < desde) return emptyList()
        val keys = mutableListOf<String>()
        var year = desde.take(4).toInt()
        var month = desde.substring(5, 7).toInt()
        while (keys.size < 1_200) {
            val key = "%04d-%02d".format(java.util.Locale.ROOT, year, month)
            if (key > hasta) break
            keys += key
            month++
            if (month > 12) { year++; month = 1 }
        }
        return keys
    }

    fun totalesEntre(libro: Libro, desde: String, hasta: String): Totales =
        totales(libro) { movement -> IsoDates.monthOf(movement.fecha).let { it.isNotEmpty() && it in desde..hasta } }

    fun cuantosMesesConDatos(libro: Libro, desde: String, hasta: String): Int = libro.movimientos.asSequence()
        .filter { it.importe != 0.0 }
        .map { IsoDates.monthOf(it.fecha) }
        .filter { it.isNotEmpty() && it in desde..hasta }
        .toSet().size

    fun resumenPeriodo(
        libro: Libro,
        desde: String,
        hasta: String,
        particion: String = POR_MESES,
    ): ResumenPeriodo {
        val actualPartition = particion.takeIf { it in setOf(POR_DIAS, POR_MESES, POR_ANIOS) } ?: POR_MESES
        val sections = when (actualPartition) {
            POR_DIAS -> tramosPorDias(libro, desde, hasta)
            POR_ANIOS -> tramosPorAnios(libro, desde, hasta)
            else -> tramosPorMeses(libro, desde, hasta)
        }
        val total = totalesEntre(libro, desde, hasta)
        return ResumenPeriodo(
            desde = desde,
            hasta = hasta,
            tramos = sections,
            total = total,
            mesesConDatos = cuantosMesesConDatos(libro, desde, hasta),
            gasto = repartoPorTipo(libro, total.porCategoria, GASTO),
            ingreso = repartoPorTipo(libro, total.porCategoria, INGRESO),
            particion = actualPartition,
        )
    }

    fun resumenAnual(libro: Libro, anio: Int): ResumenPeriodo = resumenPeriodo(
        libro,
        IsoDates.monthKey(anio, 0),
        IsoDates.monthKey(anio, 11),
        POR_MESES,
    )

    private fun tramosPorDias(libro: Libro, desde: String, hasta: String): List<Tramo> =
        mesesEntre(desde, hasta).flatMap { month ->
            IsoDates.daysOfMonth(month).map { date ->
                val day = date.takeLast(2).toInt().toString()
                Tramo(
                    clave = date,
                    nombre = "${IsoDates.weekday(date)} $day".trim(),
                    corto = day,
                    totales = totales(libro) { it.fecha == date },
                    saldoFinal = saldoHasta(libro, date),
                )
            }
        }

    private fun tramosPorMeses(libro: Libro, desde: String, hasta: String): List<Tramo> {
        val multipleYears = desde.take(4) != hasta.take(4)
        return mesesEntre(desde, hasta).map { key ->
            val index = key.substring(5, 7).toInt() - 1
            Tramo(
                clave = key,
                nombre = if (multipleYears) "${ContaXcellValues.MESES[index]} ${key.take(4)}" else ContaXcellValues.MESES[index],
                corto = if (multipleYears) "${ContaXcellValues.MESES_CORTOS[index]} ${key.substring(2, 4)}" else ContaXcellValues.MESES_CORTOS[index],
                totales = totalesDelMes(libro, key),
                saldoFinal = saldoHasta(libro, "$key-31"),
            )
        }
    }

    private fun tramosPorAnios(libro: Libro, desde: String, hasta: String): List<Tramo> {
        if (!isMonthKey(desde) || !isMonthKey(hasta) || hasta < desde) return emptyList()
        return (desde.take(4).toInt()..hasta.take(4).toInt()).map { year ->
            val first = maxOf(desde, "%04d-01".format(java.util.Locale.ROOT, year))
            val last = minOf(hasta, "%04d-12".format(java.util.Locale.ROOT, year))
            Tramo(
                clave = year.toString(), nombre = year.toString(), corto = year.toString(),
                totales = totalesEntre(libro, first, last),
                saldoFinal = saldoHasta(libro, "$last-31"),
            )
        }
    }

    private fun isMonthKey(value: String): Boolean = Regex("^\\d{4}-(0[1-9]|1[0-2])$").matches(value)

    fun repartoPorTipo(libro: Libro, porCategoria: Map<String, Double>, tipo: String): Reparto {
        val known = libro.categorias.mapTo(mutableSetOf()) { it.nombre }
        val entries = libro.categorias.filter { it.tipo == tipo }.map { it.nombre to (porCategoria[it.nombre] ?: 0.0) }.toMutableList()
        if (tipo == GASTO) {
            porCategoria.filterKeys { it !in known }.forEach { (name, value) -> entries += name to value }
        }
        val total = DomainNumbers.money(entries.sumOf { it.second })
        val rows = entries.map { (name, value) -> FilaReparto(name, value, if (total > 0) value / total else 0.0) }
            .sortedByDescending { it.importe }
        return Reparto(total, rows)
    }

    fun presupuestoDelMes(libro: Libro, mes: String): Presupuesto {
        val totals = totalesDelMes(libro, mes)
        return Presupuesto(
            mes = mes,
            filas = libro.categorias.filter { it.tipo == GASTO }.map {
                FilaPresupuesto(it.nombre, it.presupuesto, totals.porCategoria[it.nombre] ?: 0.0)
            },
            ingresos = totals.ingresos,
            aportado = totals.inversion,
            objetivoInversion = libro.ajustes.objetivoInversion,
        )
    }

    fun cartera(libro: Libro): Cartera {
        val contributions = libro.movimientos.filter { libro.tipoDe(it.categoria) == INVERSION }
        val assets = libro.activos.map { asset ->
            val bank = DomainNumbers.money(contributions.filter { it.activo == asset.nombre }.sumOf { it.importe })
            val free = DomainNumbers.money(libro.aportacionesGratis.filter { it.activo == asset.nombre }.sumOf { it.importe })
            val titles = DomainNumbers.titles(
                contributions.filter { it.activo == asset.nombre }.sumOf { it.titulos } +
                    libro.aportacionesGratis.filter { it.activo == asset.nombre }.sumOf { it.titulos },
            )
            var unvalued = asset.ultimaValoracion.isEmpty() && asset.valorMercado == 0.0
            val totalContributed = DomainNumbers.money(asset.aportacionInicial + bank + free)
            val quote = ultimaCotizacion(libro, asset.simbolo)
            val quoted = quote != null && titles > 0
            val marketValue = when {
                quoted -> DomainNumbers.money(titles * quote!!.precio)
                unvalued -> totalContributed
                else -> asset.valorMercado
            }
            val valuationDate = if (quoted) quote!!.fecha else asset.ultimaValoracion
            if (quoted) unvalued = false
            FilaActivo(
                nombre = asset.nombre,
                aportacionInicial = asset.aportacionInicial,
                aportadoBanco = bank,
                aportadoGratis = free,
                valorMercado = marketValue,
                ultimaValoracion = valuationDate,
                categoria = asset.categoria,
                titulos = titles,
                sinValorar = unvalued,
                simbolo = asset.simbolo,
                cotizado = quoted,
            )
        }
        val assignedBank = DomainNumbers.money(assets.sumOf { it.aportadoBanco })
        val assignedFree = DomainNumbers.money(assets.sumOf { it.aportadoGratis })
        return Cartera(
            activos = assets,
            historico = historico(libro, contributions),
            sinAsignarBanco = DomainNumbers.money(contributions.sumOf { it.importe } - assignedBank),
            sinAsignarGratis = DomainNumbers.money(libro.aportacionesGratis.sumOf { it.importe } - assignedFree),
        )
    }

    private fun historico(libro: Libro, contributions: List<Movimiento>): List<PuntoHistorico> {
        val initial = DomainNumbers.money(libro.activos.sumOf { it.aportacionInicial })
        return libro.historico.sortedBy { it.fecha }.map { valuation ->
            val bank = contributions.filter { it.fecha <= valuation.fecha }.sumOf { it.importe }
            val free = libro.aportacionesGratis.filter { it.fecha <= valuation.fecha }.sumOf { it.importe }
            PuntoHistorico(valuation.id, valuation.fecha, DomainNumbers.money(initial + bank + free), valuation.valorMercado)
        }
    }

    fun mayorGastoEntre(libro: Libro, desde: String, hasta: String): Movimiento? = libro.movimientos
        .filter {
            val month = IsoDates.monthOf(it.fecha)
            month.isNotEmpty() && month in desde..hasta && libro.tipoDe(it.categoria) == GASTO && it.importe > 0
        }
        .maxWithOrNull(compareBy<Movimiento> { it.importe }.thenBy { it.fecha })

    fun indicadoresDe(libro: Libro, desde: String, hasta: String, particion: String = POR_MESES): Indicadores {
        val summary = resumenPeriodo(libro, desde, hasta, particion)
        val investments = cartera(libro)
        val balance = saldoBanco(libro)
        val monthCount = summary.mesesConDatos
        val averageSpend = if (monthCount > 0) DomainNumbers.money(summary.total.gastos / monthCount) else 0.0
        val biggest = summary.tramos.maxByOrNull { it.totales.gastos }
        return Indicadores(
            desde = desde,
            hasta = hasta,
            saldoBanco = balance,
            mesesConDatos = monthCount,
            ahorroMedio = if (monthCount > 0) DomainNumbers.money(summary.total.ahorro / monthCount) else 0.0,
            gastoMedio = averageSpend,
            tasaAhorro = summary.total.tasaAhorro,
            tramoMayorGasto = biggest?.takeIf { it.totales.gastos > 0 }?.nombre.orEmpty(),
            mayorGasto = mayorGastoEntre(libro, desde, hasta),
            mesesDeColchon = if (averageSpend > 0) balance / averageSpend else 0.0,
            inversion = summary.total.inversion,
            totalAportado = investments.totalAportado,
            valorCartera = investments.valorMercado,
            generadoMercado = investments.generado,
            patrimonio = DomainNumbers.money(balance + investments.valorMercado),
        )
    }

    fun indicadores(libro: Libro, anio: Int): Indicadores = indicadoresDe(
        libro,
        IsoDates.monthKey(anio, 0),
        IsoDates.monthKey(anio, 11),
        POR_MESES,
    )

    fun aniosConDatos(libro: Libro, currentYear: Int = IsoDates.today().take(4).toInt()): List<Int> =
        (libro.movimientos.filter { IsoDates.isValid(it.fecha) }.map { IsoDates.yearOf(it.fecha) } + currentYear).distinct().sortedDescending()

    fun mesesConDatos(libro: Libro, currentMonth: String = IsoDates.monthOf(IsoDates.today())): List<String> =
        (libro.movimientos.filter { IsoDates.isValid(it.fecha) }.map { IsoDates.monthOf(it.fecha) } + currentMonth).distinct().sortedDescending()

    fun vencimiento(periodico: Periodico, numero: Int): String {
        val (days, months) = ContaXcellValues.PASO[periodico.periodo] ?: (0 to 1)
        return if (days != 0) IsoDates.plusDays(periodico.desde, days * numero)
        else IsoDates.plusMonths(periodico.desde, months * numero)
    }

    fun vencimientos(periodico: Periodico, hasta: String, desde: String = ""): List<String> {
        if (!IsoDates.isValid(periodico.desde) || !IsoDates.isValid(hasta) || hasta < periodico.desde) return emptyList()
        val limit = if (periodico.hasta.isNotEmpty()) minOf(hasta, periodico.hasta) else hasta
        return buildList {
            repeat(TOPE_VENCIMIENTOS) { number ->
                val date = vencimiento(periodico, number)
                if (date.isEmpty() || date > limit) return@buildList
                if (desde.isEmpty() || date >= desde) add(date)
            }
        }
    }

    fun proximoVencimiento(periodico: Periodico, desde: String = ""): String {
        val reference = desde.takeIf(IsoDates::isValid) ?: IsoDates.today()
        if (!IsoDates.isValid(periodico.desde)) return ""
        repeat(TOPE_VENCIMIENTOS) { number ->
            val date = vencimiento(periodico, number)
            if (date.isEmpty() || (periodico.hasta.isNotEmpty() && date > periodico.hasta)) return ""
            if (date >= reference) return date
        }
        return ""
    }

    fun estaVigente(periodico: Periodico, fecha: String = ""): Boolean {
        if (!periodico.encendido) return false
        val reference = fecha.takeIf(IsoDates::isValid) ?: IsoDates.today()
        return periodico.hasta.isEmpty() || periodico.hasta >= reference
    }

    fun costeMensual(periodico: Periodico): Double = DomainNumbers.money(
        periodico.importe * (ContaXcellValues.VECES_AL_ANIO[periodico.periodo] ?: 12) / 12,
    )

    fun pendientes(libro: Libro, hasta: String): List<Pendiente> = libro.periodicos.mapNotNull { recurring ->
        if (!recurring.encendido) return@mapNotNull null
        val start = recurring.apuntadoHasta.takeIf(String::isNotEmpty)?.let { IsoDates.plusDays(it, 1) }.orEmpty()
        vencimientos(recurring, hasta, start).takeIf(List<String>::isNotEmpty)?.let { Pendiente(recurring, it) }
    }

    /** Immutable equivalent of the desktop mutation: returns the advanced recurring rule. */
    fun saltarLoPasado(periodico: Periodico, hasta: String): Periodico {
        val lastPast = vencimientos(periodico, hasta).lastOrNull { it < hasta } ?: return periodico
        return if (lastPast > periodico.apuntadoHasta) periodico.copy(apuntadoHasta = lastPast) else periodico
    }

    /** Immutable equivalent of the desktop mutation: use [ApuntePendientes.libro] as the new state. */
    fun apuntarPendientes(libro: Libro, hasta: String): ApuntePendientes {
        val pending = pendientes(libro, hasta)
        val created = pending.flatMap { item ->
            item.fechas.map { date ->
                Movimiento(
                    fecha = date,
                    descripcion = item.periodico.nombre,
                    categoria = item.periodico.categoria,
                    importe = item.periodico.importe,
                    activo = item.periodico.activo,
                    origen = item.periodico.id,
                )
            }
        }
        val lastById = pending.associate { it.periodico.id to it.fechas.last() }
        val updatedRules = libro.periodicos.map { recurring ->
            lastById[recurring.id]?.let { recurring.copy(apuntadoHasta = it) } ?: recurring
        }
        return ApuntePendientes(libro.copy(movimientos = libro.movimientos + created, periodicos = updatedRules), created)
    }

    /** Creates a recurring rule and returns the movement linked to it, without mutating either input. */
    fun periodicoDe(movimiento: Movimiento, periodo: String, fecha: String = ""): CreacionPeriodico {
        var recurring = Periodico(
            nombre = movimiento.descripcion.trim().ifEmpty { movimiento.categoria },
            categoria = movimiento.categoria,
            importe = movimiento.importe,
            periodo = periodo,
            desde = movimiento.fecha,
            activo = movimiento.activo,
            apuntadoHasta = movimiento.fecha,
        ).normalized()
        recurring = saltarLoPasado(recurring, fecha.takeIf(IsoDates::isValid) ?: IsoDates.today())
        return CreacionPeriodico(movimiento.copy(origen = recurring.id), recurring)
    }

    fun resumenPeriodicos(libro: Libro, fecha: String = ""): ResumenPeriodicos {
        var enabled = 0
        var disabled = 0
        var finished = 0
        var spend = 0.0
        var income = 0.0
        var investment = 0.0
        libro.periodicos.forEach { recurring ->
            if (!estaVigente(recurring, fecha)) {
                if (recurring.encendido) finished++ else disabled++
            } else {
                enabled++
                val monthly = costeMensual(recurring)
                when (libro.tipoDe(recurring.categoria)) {
                    INGRESO -> income = DomainNumbers.money(income + monthly)
                    INVERSION -> investment = DomainNumbers.money(investment + monthly)
                    else -> spend = DomainNumbers.money(spend + monthly)
                }
            }
        }
        return ResumenPeriodicos(enabled, disabled, finished, spend, income, investment)
    }

    fun apuntadosPor(libro: Libro, periodico: Periodico): Int = libro.movimientos.count { it.origen == periodico.id }

    fun pendienteDe(deuda: Deuda): Double = maxOf(DomainNumbers.money(deuda.importe - deuda.devuelto), 0.0)

    fun estaSaldada(deuda: Deuda): Boolean = pendienteDe(deuda) <= 0.0

    /** Immutable payment annotation. [PagoDeuda.apuntado] is capped at the outstanding balance. */
    fun anotarPago(deuda: Deuda, importe: Double, hastaElFinal: Boolean = false): PagoDeuda {
        val outstanding = pendienteDe(deuda)
        val amount = if (hastaElFinal) outstanding else minOf(kotlin.math.abs(DomainNumbers.money(importe)), outstanding)
        return PagoDeuda(deuda.copy(devuelto = DomainNumbers.money(deuda.devuelto + amount)), amount)
    }

    fun resumenDeudas(libro: Libro): ResumenDeudas {
        var owedToYou = 0.0
        var youOwe = 0.0
        var open = 0
        var settled = 0
        val people = mutableSetOf<String>()
        libro.deudas.forEach { debt ->
            if (estaSaldada(debt)) {
                settled++
            } else {
                open++
                people += debt.quien.lowercase(java.util.Locale.ROOT)
                if (debt.sentido == ContaXcellValues.ME_DEBEN) {
                    owedToYou = DomainNumbers.money(owedToYou + pendienteDe(debt))
                } else {
                    youOwe = DomainNumbers.money(youOwe + pendienteDe(debt))
                }
            }
        }
        return ResumenDeudas(owedToYou, youOwe, open, settled, people.size)
    }

    fun deudasPorPersona(libro: Libro): List<SaldoConPersona> {
        data class MutableBalance(
            val name: String,
            var owedToYou: Double = 0.0,
            var youOwe: Double = 0.0,
            var count: Int = 0,
        )
        val balances = linkedMapOf<String, MutableBalance>()
        libro.deudas.forEach { debt ->
            if (estaSaldada(debt) || debt.quien.isEmpty()) return@forEach
            val key = debt.quien.lowercase(java.util.Locale.ROOT)
            val balance = balances.getOrPut(key) { MutableBalance(debt.quien) }
            balance.count++
            if (debt.sentido == ContaXcellValues.ME_DEBEN) {
                balance.owedToYou = DomainNumbers.money(balance.owedToYou + pendienteDe(debt))
            } else {
                balance.youOwe = DomainNumbers.money(balance.youOwe + pendienteDe(debt))
            }
        }
        return balances.values.map { SaldoConPersona(it.name, it.owedToYou, it.youOwe, it.count) }
            .sortedWith(compareByDescending<SaldoConPersona> { it.neto }.thenBy { it.quien.lowercase(java.util.Locale.ROOT) })
    }

    fun comprasDe(libro: Libro, nombreActivo: String): List<Compra> {
        val asset = cartera(libro).activos.firstOrNull { it.nombre == nombreActivo } ?: return emptyList()
        val price = if (asset.sinValorar) 0.0 else asset.precioHoy
        val symbol = libro.activo(nombreActivo)?.simbolo.orEmpty()
        val currentQuote = ultimaCotizacion(libro, symbol)?.precio
        return libro.movimientos.asSequence()
            .filter { it.activo == nombreActivo && it.titulos > 0 && libro.tipoDe(it.categoria) == INVERSION }
            .map {
                Compra(
                    it.id, it.fecha, it.descripcion, it.importe, it.titulos, price,
                    quoteAtPurchase = ultimaCotizacion(libro, symbol, it.fecha)?.precio,
                    quoteToday = currentQuote,
                )
            }
            .sortedWith(compareByDescending<Compra> { it.fecha }.thenByDescending { it.id })
            .toList()
    }

    fun porCategoria(cartera: Cartera): List<GrupoCartera> {
        val total = cartera.valorMercado
        return cartera.activos.groupBy { it.categoria.ifEmpty { SIN_CATEGORIA } }
            .map { (category, assets) ->
                val group = GrupoCartera(category, assets)
                group.copy(peso = if (total > 0) group.valorMercado / total else 0.0)
            }
            .sortedByDescending { it.valorMercado }
    }

    fun cotizacionesDe(libro: Libro, simbolo: String): List<Cotizacion> {
        val code = simbolo.trim().uppercase(java.util.Locale.ROOT)
        if (code.isEmpty()) return emptyList()
        return libro.cotizaciones.filter { it.simbolo == code }.sortedBy { it.fecha }
    }

    fun ultimaCotizacion(libro: Libro, simbolo: String, hasta: String = ""): Cotizacion? =
        cotizacionesDe(libro, simbolo).lastOrNull { hasta.isEmpty() || it.fecha <= hasta }

    /** Immutable merge; same-date server corrections replace the previous close. */
    fun guardarCotizaciones(libro: Libro, simbolo: String, nuevas: List<Cotizacion>): ActualizacionCotizaciones {
        val code = simbolo.trim().uppercase(java.util.Locale.ROOT)
        if (code.isEmpty()) return ActualizacionCotizaciones(libro, 0)
        val byDate = libro.cotizaciones.filter { it.simbolo == code }.associateByTo(linkedMapOf()) { it.fecha }
        val before = byDate.size
        nuevas.map(Cotizacion::normalized).filter { it.fecha.isNotEmpty() && it.precio > 0 }.forEach { quote ->
            byDate[quote.fecha] = quote.copy(simbolo = code)
        }
        val other = libro.cotizaciones.filter { it.simbolo != code }
        val merged = other + byDate.toSortedMap().values
        return ActualizacionCotizaciones(libro.copy(cotizaciones = merged), byDate.size - before)
    }

    fun simbolosDelLibro(libro: Libro): List<String> {
        val seen = linkedSetOf<String>()
        libro.activos.forEach { asset ->
            asset.simbolo.trim().uppercase(java.util.Locale.ROOT).takeIf(String::isNotEmpty)?.let(seen::add)
        }
        return seen.toList()
    }

    fun desdeCuandoHacenFalta(libro: Libro, simbolo: String, hoy: String = IsoDates.today()): String {
        val code = simbolo.trim().uppercase(java.util.Locale.ROOT)
        val names = libro.activos.filter { it.simbolo.trim().uppercase(java.util.Locale.ROOT) == code }.mapTo(mutableSetOf()) { it.nombre }
        val dates = libro.movimientos.filter { it.activo in names && IsoDates.isValid(it.fecha) }.map { it.fecha } +
            libro.aportacionesGratis.filter { it.activo in names && IsoDates.isValid(it.fecha) }.map { it.fecha }
        return dates.minOrNull() ?: hoy
    }
}
