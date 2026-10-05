package com.contaxcell.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.contaxcell.app.ui.ContaXcellApp

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    private val importTradeRepublic = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { contentResolver.openInputStream(it)?.use(viewModel::importTradeRepublic) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val state by viewModel.state.collectAsStateWithLifecycle()
            LaunchedEffect(viewModel) {
                viewModel.effects.collect { effect ->
                    when (effect) {
                        AppEffect.ChooseTradeRepublicPdf -> importTradeRepublic.launch(arrayOf(PDF_MIME))
                    }
                }
            }
            ContaXcellApp(state = state, onAction = viewModel::dispatch)
        }
    }

    private companion object {
        const val PDF_MIME = "application/pdf"
    }
}
