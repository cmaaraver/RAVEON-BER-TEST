# Raveon RV-M21 BER Tester & Auto-Configurator

Herramienta desarrollada en Python para la medición en tiempo real de la Tasa de Error de Bits (BER) y la configuración automática de frecuencias en radio módems Raveon Tech Series (RV-M21).

Este proyecto automatiza el proceso de configuración mediante comandos AT y realiza un análisis de integridad de datos bit a bit, ideal para validar enlaces de radiofrecuencia (RF).

 Características Principales

 Auto-Detección de Hardware: Escaneo automático de puertos seriales para identificar chips FTDI/Raveon sin intervención manual.

 Configuración Automática (AT): Inyecta la configuración de frecuencias cruzadas (Split Frequency) para establecer un enlace Full-Duplex o Half-Duplex simulado.

 Medición de BER en Tiempo Real: Cálculo preciso de errores utilizando comparación lógica XOR bit a bit.

 Sincronización Robusta: Implementación de cabeceras de sincronización (SYNC_HEADER) para recuperar tramas incluso en entornos ruidosos.

 Soporte Multiplataforma: Funciona nativamente en Windows y Linux (con gestión automática de permisos en /dev/ttyUSB).

 Requisitos de Hardware

2x Radio Módems Raveon RV-M21 (o compatibles de la serie Tech).

Antenas adecuadas para la banda de frecuencia (UHF/VHF).

PC/Laptop con puertos USB o Adaptadores Seriales.

Fuente de alimentación (si no se alimentan por USB/DB9).

 Instalación

Clonar el repositorio:

```bash
git clone https://github.com/tu-usuario/raveon-ber-tester.git
cd raveon-ber-tester
```

Instalar dependencias:
Este script requiere Python 3 y la librería pyserial.

```bash
pip install pyserial
```

Configuración Linux (Opcional):
Si usas Linux y tienes problemas de permisos:

```bash
sudo usermod -aG dialout $USER
```

# O ejecuta el script con sudo temporalmente

 Guía de Uso

El sistema funciona con dos roles: Módem A y Módem B. El script configura las frecuencias cruzadas para que puedan comunicarse.

Paso 1: Configuración de Frecuencias

Rol

Frecuencia TX (Envío)

Frecuencia RX (Escucha)

Módem A

433.000 MHz

430.000 MHz

Módem B

430.000 MHz

433.000 MHz

Paso 2: Ejecución

Ejecuta el script en dos terminales diferentes (o dos PCs), una para cada módem.

```bash
python3 TEST_BER_RAVEON.py
```

El programa detectará el puerto COM/TTY automáticamente.

Selecciona el Rol (A o B) para configurar las frecuencias automáticamente.

Selecciona el Modo de Prueba:

En una terminal: Opción 1 (Transmisor).

En la otra terminal: Opción 2 (Receptor).

 ¿Cómo funciona el cálculo de BER?

A diferencia de herramientas simples que solo cuentan paquetes perdidos, este software analiza la integridad de cada bit.

1. Generación Determinista de Patrones

Tanto el Transmisor (TX) como el Receptor (RX) comparten un algoritmo generador de patrones pseudo-aleatorios (PRNG) idéntico. No se envían datos al azar; se envía una secuencia conocida:

Secuencia = [0, 1, 2, ..., 255, 0, 1, ...]

2. Sincronización de Trama

El aire es un medio ruidoso. Para saber dónde empieza un dato válido, el TX envía una firma digital de 4 bytes antes de cada carga útil:
SYNC_HEADER = 0xAA 0x55 0xAA 0x55

El RX descarta todo el ruido hasta que detecta esta firma exacta.

3. Comparación XOR (Bit a Bit)

Cuando el RX recibe un byte, lo compara con el byte que debería haber llegado según la secuencia matemática. Se utiliza la operación lógica XOR:

Si Bit_Recibido == Bit_Esperado → XOR es 0 (Correcto).

Si Bit_Recibido != Bit_Esperado → XOR es 1 (Error).

Ejemplo:

Esperado (5):  00000101  
Recibido (4):  00000100  <-- Error inducido por ruido RF  
-----------------------  
Resultado XOR: 00000001  --> 1 Bit Erróneo detectado

4. Fórmula Final

```text
BER = Total Bits Erróneos / Total Bits Recibidos
```

 Ejemplo de Salida

En el Receptor:

=== CONFIGURADOR Y TESTER RAVEON RV-M21 ===
 -> ENCONTRADO: /dev/ttyUSB0 (FT231X USB UART)
Usando puerto: /dev/ttyUSB0

[RX] Esperando datos...
[RX] Pkts: 150 | Err: 0 | BER: 0.000000
[RX] Pkts: 151 | Err: 1 | BER: 0.000082
...

 Solución de Problemas

"Permission denied" en Linux:
El usuario no tiene acceso al puerto serial. Solución rápida:

```bash
sudo chmod 666 /dev/ttyUSB0
```

BER del 50% (0.5):
Significa que los datos son totalmente aleatorios. Verifica que ambos módems tengan la configuración de frecuencias cruzada (A vs B) y la misma velocidad (Baudrate).

No se reciben datos:
Asegúrate de haber salido del "Modo Comandos". El script lo hace automáticamente enviando el comando:

```bash
EXIT
```

pero si se interrumpió, reinicia el módem eléctricamente.

 Autor: Carlos Maraver

Proyecto desarrollado para validación técnica de enlaces UHF/VHF.
