package com.contaxcell.app.ui

import com.contaxcell.app.ui.components.isAllowedNumber
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NumericInputTest {
    @Test
    fun acceptsSpanishMoneyAndPastedFormatting() {
        assertTrue(isAllowedNumber(""))
        assertTrue(isAllowedNumber("1234"))
        assertTrue(isAllowedNumber("1.234,56"))
        assertTrue(isAllowedNumber("1.234,56 \u20ac"))
    }

    @Test
    fun rejectsLettersRepeatedCommaAndOverlongPaste() {
        assertFalse(isAllowedNumber("12 euros"))
        assertFalse(isAllowedNumber("1,2,3"))
        assertFalse(isAllowedNumber("123456789012345678901"))
    }

    @Test
    fun negativeSignIsOnlyAllowedAtTheBeginningWhenRequested() {
        assertFalse(isAllowedNumber("-12"))
        assertTrue(isAllowedNumber("-12,50", allowNegative = true))
        assertFalse(isAllowedNumber("12-50", allowNegative = true))
        assertFalse(isAllowedNumber("--12", allowNegative = true))
    }
}
