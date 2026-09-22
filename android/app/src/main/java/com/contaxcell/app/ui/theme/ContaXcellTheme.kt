package com.contaxcell.app.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import com.contaxcell.app.ui.ThemePreference

val Expense = Color(0xFFB42318)
val ExpenseDark = Color(0xFFFF8A80)
val Income = Color(0xFF067647)
val IncomeDark = Color(0xFF5DDB9D)
val Investment = Color(0xFF6941C6)
val InvestmentDark = Color(0xFFC5A7FF)
val Warning = Color(0xFFB54708)

private val LightColors = lightColorScheme(
    primary = Color(0xFF2459D3),
    onPrimary = Color(0xFFF9FAFF),
    primaryContainer = Color(0xFFDCE5FF),
    onPrimaryContainer = Color(0xFF102C70),
    secondary = Color(0xFF4D5D7C),
    onSecondary = Color(0xFFF9FAFF),
    background = Color(0xFFF4F6FA),
    onBackground = Color(0xFF171A21),
    surface = Color(0xFFFCFCFE),
    onSurface = Color(0xFF171A21),
    surfaceVariant = Color(0xFFE9ECF2),
    onSurfaceVariant = Color(0xFF565E6D),
    outline = Color(0xFFCBD0D9),
    outlineVariant = Color(0xFFE0E3E9),
    error = Expense,
    onError = Color.White,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9CB7FF),
    onPrimary = Color(0xFF102C70),
    primaryContainer = Color(0xFF1E3D83),
    onPrimaryContainer = Color(0xFFDCE5FF),
    secondary = Color(0xFFBAC6E4),
    onSecondary = Color(0xFF25304A),
    background = Color(0xFF12151A),
    onBackground = Color(0xFFE9EBF0),
    surface = Color(0xFF1A1E24),
    onSurface = Color(0xFFE9EBF0),
    surfaceVariant = Color(0xFF252A32),
    onSurfaceVariant = Color(0xFFB7BEC9),
    outline = Color(0xFF424954),
    outlineVariant = Color(0xFF303640),
    error = ExpenseDark,
    onError = Color(0xFF5D0000),
)

private val ContaTypography = androidx.compose.material3.Typography(
    displaySmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 36.sp,
        lineHeight = 40.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = (-0.6).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 28.sp,
        lineHeight = 34.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = (-0.35).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 22.sp,
        lineHeight = 28.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = (-0.15).sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 18.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 15.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 14.sp,
        lineHeight = 18.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        fontWeight = FontWeight.Medium,
    ),
)

private val ContaShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(9.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(14.dp),
    extraLarge = RoundedCornerShape(18.dp),
)

@Composable
fun ContaXcellTheme(
    preference: ThemePreference,
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val systemDark = isSystemInDarkTheme()
    val dark = when (preference) {
        ThemePreference.System -> systemDark
        ThemePreference.Light -> false
        ThemePreference.Dark -> true
    }
    val context = LocalContext.current
    val colors = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && dark ->
            dynamicDarkColorScheme(context)
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            dynamicLightColorScheme(context)
        dark -> DarkColors
        else -> LightColors
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        val window = (view.context as? Activity)?.window
        if (window != null) {
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !dark
        }
    }

    MaterialTheme(
        colorScheme = colors,
        typography = ContaTypography,
        shapes = ContaShapes,
        content = content,
    )
}
