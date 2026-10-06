"""El actualizador: que solo instale lo firmado y que nunca rompa nada.

Sin red: el servidor es de mentira y la llave, una de usar y tirar hecha al
empezar (la de verdad no sale del ordenador de quien publica). Que la firma
casa con una librería criptográfica de verdad se comprobó a mano con
`cryptography`, en los dos sentidos.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import actualizar, firma  # noqa: E402

SERVIDOR = "https://servidor.prueba"


class Respuesta:
    def __init__(self, datos: bytes):
        self.datos = datos

    def read(self, _limite=None):
        return self.datos

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def servidor_falso(archivos: dict[str, bytes]):
    """Contesta lo que haya en `archivos` por ruta, y 404 a lo demás."""
    pedidas = []

    def abrir(peticion, timeout=None):
        ruta = peticion.full_url[len(SERVIDOR):]
        pedidas.append(ruta)
        if ruta not in archivos:
            raise urllib.error.HTTPError(peticion.full_url, 404, "no", {}, io.BytesIO(b""))
        return Respuesta(archivos[ruta])

    abrir.pedidas = pedidas
    return abrir


def zip_de_contaxcell(con_exe: bool = True) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as z:
        if con_exe:
            z.writestr("ContaXcell/ContaXcell.exe", b"MZ programa nuevo")
        z.writestr("ContaXcell/recursos-internos/algo.dll", b"dll")
    return memoria.getvalue()


class ConLlave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1024 bits: de sobra para probar y mucho más rápida de hacer.
        cls.llave = firma.generar_llave(1024)
        cls.publica = (cls.llave["n"], cls.llave["e"])

    def publicado(self, version="1.2.0", datos_zip=None, notas="Cosas nuevas", **cambios):
        datos_zip = zip_de_contaxcell() if datos_zip is None else datos_zip
        nota = {"version": version, "archivo": f"/api/actualizacion/ContaXcell-windows-{version}.zip",
                "tamano": len(datos_zip), "sha256": hashlib.sha256(datos_zip).hexdigest(),
                "notas": notas, **cambios}
        texto = json.dumps(nota).encode("utf-8")
        return {
            actualizar.RUTA_NOTA: texto,
            actualizar.RUTA_FIRMA: firma.firmar(texto, self.llave),
            nota["archivo"]: datos_zip,
        }


class PruebaFirma(ConLlave):
    def test_firma_y_comprueba(self):
        f = firma.firmar(b"hola", self.llave)
        self.assertTrue(firma.comprobar(b"hola", f, self.publica))

    def test_rechaza_lo_tocado(self):
        f = bytearray(firma.firmar(b"hola", self.llave))
        self.assertFalse(firma.comprobar(b"hola!", bytes(f), self.publica))
        f[-1] ^= 1
        self.assertFalse(firma.comprobar(b"hola", bytes(f), self.publica))
        self.assertFalse(firma.comprobar(b"hola", b"corta", self.publica))

    def test_rechaza_la_de_otra_llave(self):
        otra = firma.generar_llave(1024)
        self.assertFalse(firma.comprobar(b"hola", firma.firmar(b"hola", otra), self.publica))

    def test_la_llave_del_programa_es_de_verdad(self):
        from contaxcell.llave_publica import LLAVE_PUBLICA
        self.assertEqual(LLAVE_PUBLICA[0].bit_length(), 3072)
        self.assertEqual(LLAVE_PUBLICA[1], 65537)


class PruebaVersiones(unittest.TestCase):
    def test_se_comparan_como_numeros(self):
        self.assertTrue(actualizar.es_mas_nueva("1.10.0", "1.9.3"))
        self.assertTrue(actualizar.es_mas_nueva("1.1", "1.0.9"))
        self.assertTrue(actualizar.es_mas_nueva("2.0.0", "1.99"))
        self.assertFalse(actualizar.es_mas_nueva("1.1.0", "1.1"))
        self.assertFalse(actualizar.es_mas_nueva("1.0.0", "1.1.0"))


class PruebaBuscar(ConLlave):
    def test_sin_nada_publicado_no_hay_nada(self):
        self.assertIsNone(actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso({}), self.publica))

    def test_una_mas_nueva_se_ofrece(self):
        novedad = actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(self.publicado()), self.publica)
        self.assertEqual((novedad.version, novedad.notas), ("1.2.0", "Cosas nuevas"))

    def test_la_misma_o_una_vieja_no(self):
        for version in ("1.1.0", "1.0.5"):
            with self.subTest(version):
                self.assertIsNone(actualizar.buscar(
                    SERVIDOR, "1.1.0", servidor_falso(self.publicado(version)), self.publica))

    def test_una_nota_cambiada_en_el_servidor_no_se_cree(self):
        archivos = self.publicado()
        archivos[actualizar.RUTA_NOTA] = archivos[actualizar.RUTA_NOTA].replace(b"1.2.0", b"9.9.9")
        with self.assertRaises(actualizar.ActualizacionNoFiable):
            actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica)

    def test_firmada_por_otro_no_se_cree(self):
        otra = firma.generar_llave(1024)
        archivos = self.publicado()
        archivos[actualizar.RUTA_FIRMA] = firma.firmar(archivos[actualizar.RUTA_NOTA], otra)
        with self.assertRaises(actualizar.ActualizacionNoFiable):
            actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica)

    def test_sin_firma_no_se_cree(self):
        archivos = self.publicado()
        del archivos[actualizar.RUTA_FIRMA]
        self.assertIsNone(actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica))

    def test_un_archivo_fuera_de_su_sitio_no_se_acepta(self):
        archivos = self.publicado(archivo="/descargas/ContaXcell-windows-1.2.0.zip")
        with self.assertRaises(actualizar.ActualizacionNoFiable):
            actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica)

    def test_pregunta_con_la_ficha_de_la_sesion(self):
        fichas = []

        def con_ficha(peticion, timeout=None):
            fichas.append(peticion.get_header("Authorization"))
            return servidor_falso(self.publicado())(peticion, timeout)

        actualizar.buscar(SERVIDOR, "1.1.0", con_ficha, self.publica, token="abc")
        self.assertEqual(fichas, ["Bearer abc", "Bearer abc"])

    def test_cuenta_en_espera_o_vetada_no_recibe_nada(self):
        for codigo in (401, 403):
            def sin_permiso(peticion, timeout=None, codigo=codigo):
                raise urllib.error.HTTPError(peticion.full_url, codigo, "no", {}, io.BytesIO(b""))
            with self.subTest(codigo), self.assertRaises(actualizar.SinPermiso):
                actualizar.buscar(SERVIDOR, "1.1.0", sin_permiso, self.publica, token="abc")

    def test_trae_la_lista_de_cambios_y_el_enlace(self):
        archivos = self.publicado(
            cambios=[{"titulo": "Lo nuevo", "detalle": "Con su porqué"},
                     {"titulo": "Un arreglo"}, {"titulo": "", "detalle": "sin título"}],
            codigo="https://github.com/ana/Conta/compare/a...b")
        novedad = actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica)
        self.assertEqual(novedad.cambios, (("Lo nuevo", "Con su porqué"), ("Un arreglo", "")))
        self.assertEqual(novedad.codigo, "https://github.com/ana/Conta/compare/a...b")

    def test_las_notas_de_antes_sin_cambios_valen_igual(self):
        novedad = actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(self.publicado()), self.publica)
        self.assertEqual((novedad.cambios, novedad.codigo), ((), ""))

    def test_un_enlace_que_no_es_de_github_no_se_abre(self):
        archivos = self.publicado(codigo="https://otro-sitio.example/malo")
        novedad = actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica)
        self.assertEqual(novedad.codigo, "")

    def test_sin_red_lo_dice_sin_romper(self):
        def sin_red(peticion, timeout=None):
            raise urllib.error.URLError("sin red")
        with self.assertRaises(actualizar.SinActualizaciones):
            actualizar.buscar(SERVIDOR, "1.1.0", sin_red, self.publica)


class PruebaDescargarYPreparar(ConLlave):
    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporal.cleanup)
        self.trabajo = Path(self._temporal.name) / "trabajo"

    def novedad(self, archivos):
        return actualizar.buscar(SERVIDOR, "1.1.0", servidor_falso(archivos), self.publica)

    def test_baja_el_zip_si_es_el_de_la_nota(self):
        archivos = self.publicado()
        archivo = actualizar.descargar(SERVIDOR, self.novedad(archivos), self.trabajo,
                                       servidor_falso(archivos))
        self.assertEqual(archivo.read_bytes(), archivos["/api/actualizacion/ContaXcell-windows-1.2.0.zip"])

    def test_un_zip_cambiado_no_se_guarda(self):
        archivos = self.publicado()
        novedad = self.novedad(archivos)
        archivos[novedad.archivo] = zip_de_contaxcell(con_exe=False)
        with self.assertRaises(actualizar.ActualizacionNoFiable):
            actualizar.descargar(SERVIDOR, novedad, self.trabajo, servidor_falso(archivos))
        self.assertEqual(list(self.trabajo.glob("*.zip")), [])

    def test_prepara_el_cambio(self):
        archivos = self.publicado()
        archivo = actualizar.descargar(SERVIDOR, self.novedad(archivos), self.trabajo,
                                       servidor_falso(archivos))
        instalacion = Path(self._temporal.name) / "Programas de Begoña" / "ContaXcell"
        guion = actualizar.preparar(archivo, instalacion, 4321, self.trabajo)
        texto = guion.read_text(encoding="utf-8-sig")
        self.assertTrue(guion.read_bytes().startswith(b"\xef\xbb\xbf"))  # con BOM, por las eñes
        self.assertIn("Wait-Process -Id 4321", texto)
        self.assertIn("robocopy", texto)
        self.assertIn(str(instalacion / "ContaXcell.exe"), texto)
        self.assertTrue((self.trabajo / "nueva" / "ContaXcell" / "ContaXcell.exe").is_file())
        # El cartel de «Reiniciando…», que sale hasta que se abre el nuevo.
        self.assertIn("Reiniciando ContaXcell", texto)
        self.assertIn("CenterScreen", texto)

    def test_el_cartel_sale_en_la_pantalla_del_programa(self):
        archivos = self.publicado()
        archivo = actualizar.descargar(SERVIDOR, self.novedad(archivos), self.trabajo,
                                       servidor_falso(archivos))
        texto = actualizar.preparar(archivo, Path(self._temporal.name), 1, self.trabajo,
                                    centro=(2900, 500)).read_text(encoding="utf-8-sig")
        self.assertIn("(2900 - $ancho / 2)", texto)
        self.assertNotIn("CenterScreen", texto)

    def test_una_ruta_con_comilla_no_rompe_el_guion(self):
        archivos = self.publicado()
        archivo = actualizar.descargar(SERVIDOR, self.novedad(archivos), self.trabajo,
                                       servidor_falso(archivos))
        instalacion = Path(self._temporal.name) / "D'Artagnan"
        texto = actualizar.preparar(archivo, instalacion, 1, self.trabajo).read_text(encoding="utf-8-sig")
        self.assertIn("D''Artagnan", texto)

    def test_un_zip_sin_contaxcell_no_se_prepara(self):
        ruta = self.trabajo / "raro.zip"
        self.trabajo.mkdir(parents=True)
        ruta.write_bytes(zip_de_contaxcell(con_exe=False))
        with self.assertRaises(actualizar.ActualizacionNoFiable):
            actualizar.preparar(ruta, Path(self._temporal.name), 1, self.trabajo)

    def test_un_zip_que_se_sale_de_su_carpeta_no_se_prepara(self):
        memoria = io.BytesIO()
        with zipfile.ZipFile(memoria, "w") as z:
            z.writestr("ContaXcell/ContaXcell.exe", b"MZ")
            z.writestr("../../fuera.txt", b"malo")
        ruta = self.trabajo / "malo.zip"
        self.trabajo.mkdir(parents=True)
        ruta.write_bytes(memoria.getvalue())
        with self.assertRaises(actualizar.ActualizacionNoFiable):
            actualizar.preparar(ruta, Path(self._temporal.name), 1, self.trabajo)


if __name__ == "__main__":
    unittest.main()
