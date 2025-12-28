# whatsapp_bot.py
from flask import Flask, request, jsonify
import anthropic
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Configuración
EVOLUTION_URL = "https://evolution-whatsapp-zoj6.onrender.com"
EVOLUTION_TOKEN = "mitoken1234"
INSTANCE_NAME = "mi-bot-prueba"
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Almacenar conversaciones
conversaciones = {}

# === RESPUESTAS EN CACHÉ (sin costo de API) ===
RESPUESTAS_CACHE = {
    "hola": "¡Hola! 👋 Soy el asistente virtual. ¿En qué puedo ayudarte hoy?\n\nPuedo informarte sobre:\n• Servicios de desarrollo web\n• Planes y precios\n• Chatbots con IA\n• Hosting y mantenimiento",
    
    "precio": "💰 Nuestros planes de suscripción:\n\n📦 Básico - $59.990/mes\n• Sitio web profesional\n• 3 horas soporte/mes\n• Hosting incluido\n\n🚀 Profesional - $99.990/mes\n• Todo lo anterior\n• 6 horas soporte/mes\n• SEO + Blog\n• Chatbot básico\n\n⭐ Premium - $149.990/mes\n• Todo lo anterior\n• 10 horas soporte/mes\n• Marketing digital\n• Chatbot avanzado",
    
    "precios": "💰 Nuestros planes de suscripción:\n\n📦 Básico - $59.990/mes\n🚀 Profesional - $99.990/mes\n⭐ Premium - $149.990/mes\n\n¿Quieres más detalles de algún plan?",
    
    "cuanto cuesta": "Tenemos 3 planes:\n• Básico: $59.990/mes\n• Profesional: $99.990/mes\n• Premium: $149.990/mes\n\n¿Te gustaría conocer qué incluye cada uno?",
    
    "horario": "🕐 Atención:\n• Chatbot 24/7 (siempre disponible)\n• Soporte humano: Lunes a Viernes 9:00-18:00 hrs\n\n¿En qué puedo ayudarte?",
    
    "servicios": "🛠️ Nuestros servicios:\n\n• Desarrollo web (WordPress, Shopify)\n• Diseño UI/UX personalizado\n• E-commerce completo\n• Chatbots con IA\n• SEO y Marketing Digital\n• Hosting y mantenimiento\n• Suscripción mensual todo incluido\n\n¿Qué servicio te interesa?",
    
    "contacto": "📞 Contáctanos:\n\n• WhatsApp: Este mismo chat\n• Email: contacto@tuagencia.cl\n• Web: www.tuagencia.cl\n\n¿Quieres agendar una reunión?",
    
    "chatbot": "🤖 Chatbots con IA:\n\nImplementamos asistentes virtuales para WhatsApp que:\n✅ Responden 24/7\n✅ Aprenden de tu negocio\n✅ Califican leads\n✅ Automatizan ventas\n\n📊 Planes chatbot:\n• Básico: +$20.000/mes (100 conversaciones)\n• Pro: +$40.000/mes (500 conversaciones)\n• Ilimitado: +$80.000/mes\n\n¿Te interesa una demo?",
}

def buscar_en_cache(mensaje):
    """Busca respuesta en caché sin usar API"""
    mensaje_lower = mensaje.lower().strip()
    
    # Búsqueda exacta
    if mensaje_lower in RESPUESTAS_CACHE:
        print(f"[CACHÉ HIT] Respuesta encontrada: {mensaje_lower}")
        return RESPUESTAS_CACHE[mensaje_lower]
    
    # Búsqueda por palabras clave
    palabras_clave = {
        "hola": ["hola", "buenos dias", "buenas tardes", "buenas noches", "hey", "hi"],
        "precio": ["precio", "precios", "cuanto", "costo", "valor", "plan"],
        "horario": ["horario", "cuando atienden", "hora", "disponible"],
        "servicios": ["servicio", "que hacen", "que ofrecen", "trabajan"],
        "contacto": ["contacto", "contactar", "email", "telefono", "hablar"],
        "chatbot": ["chatbot", "bot", "automatizacion", "asistente virtual"],
    }
    
    for clave, palabras in palabras_clave.items():
        if any(palabra in mensaje_lower for palabra in palabras):
            print(f"[CACHÉ HIT] Por palabra clave: {clave}")
            return RESPUESTAS_CACHE.get(clave)
    
    return None

def elegir_modelo(mensaje):
    """Selecciona modelo según complejidad de la pregunta"""
    
    # Palabras que indican preguntas simples (usar Haiku = barato)
    palabras_simples = [
        'hola', 'precio', 'horario', 'servicios', 'contacto', 'cuanto',
        'cuando', 'donde', 'quien', 'que es', 'gracias', 'ok', 'si', 'no'
    ]
    
    # Palabras que indican preguntas complejas (usar Sonnet = mejor)
    palabras_complejas = [
        'como hacer', 'necesito ayuda', 'problema', 'error', 'integrar',
        'personalizado', 'especifico', 'comparar', 'diferencia', 'recomendar'
    ]
    
    mensaje_lower = mensaje.lower()
    
    # Si es pregunta compleja, usar Sonnet
    if any(palabra in mensaje_lower for palabra in palabras_complejas):
        print(f"[MODELO] Usando Sonnet (pregunta compleja)")
        return "claude-sonnet-4-20250514"
    
    # Si es pregunta simple, usar Haiku
    if any(palabra in mensaje_lower for palabra in palabras_simples):
        print(f"[MODELO] Usando Haiku (pregunta simple)")
        return "claude-haiku-4-20250514"
    
    # Por defecto, Haiku (más barato)
    print(f"[MODELO] Usando Haiku (default)")
    return "claude-haiku-4-20250514"

def obtener_historial(numero):
    """Obtiene el historial de conversación"""
    if numero not in conversaciones:
        conversaciones[numero] = []
    return conversaciones[numero]

def guardar_mensaje(numero, role, content):
    """Guarda mensaje en historial"""
    if numero not in conversaciones:
        conversaciones[numero] = []
    
    conversaciones[numero].append({
        "role": role,
        "content": content
    })
    
    # Limitar a últimos 10 mensajes (reducir tokens = reducir costo)
    if len(conversaciones[numero]) > 10:
        conversaciones[numero] = conversaciones[numero][-10:]

def consultar_claude(mensaje, numero):
    """Consulta a Claude API con optimización de costos"""
    
    # 1. PRIMERO: Buscar en caché (gratis)
    respuesta_cache = buscar_en_cache(mensaje)
    if respuesta_cache:
        return respuesta_cache
    
    # 2. Si no está en caché, usar Claude API
    guardar_mensaje(numero, "user", mensaje)
    
    try:
        # Elegir modelo según complejidad
        modelo = elegir_modelo(mensaje)
        
        # Llamar a Claude
        response = client.messages.create(
            model=modelo,
            max_tokens=512,  # Reducido de 1024 para ahorrar costos
            system="""Eres un asistente virtual de una agencia de desarrollo web chilena.

SERVICIOS:
- Desarrollo web WordPress/Shopify
- Diseño personalizado
- E-commerce
- Chatbots con IA para WhatsApp
- SEO y marketing
- Hosting y mantenimiento

PLANES DE SUSCRIPCIÓN WEB:
- Básico: $59.990/mes (sitio + 3hrs soporte + hosting)
- Profesional: $99.990/mes (todo anterior + 6hrs + SEO + chatbot básico)
- Premium: $149.990/mes (todo anterior + 10hrs + marketing + chatbot avanzado)

PLANES CHATBOT ADICIONAL:
- Básico: +$20.000/mes (100 conversaciones)
- Pro: +$40.000/mes (500 conversaciones)
- Ilimitado: +$80.000/mes

HORARIO:
- Chatbot 24/7
- Soporte humano: Lunes-Viernes 9-18hrs

CONTACTO:
- WhatsApp: Este chat
- Email: contacto@tuagencia.cl

INSTRUCCIONES:
- Responde en español de Chile
- Sé breve y directo (máximo 3 párrafos)
- Usa emojis con moderación
- Si preguntan por precios, menciona los planes
- Si quieren contratar, pide email o nombre para contacto
- Enfócate en beneficios del cliente""",
            messages=conversaciones[numero]
        )
        
        respuesta = response.content[0].text
        
        # Guardar respuesta
        guardar_mensaje(numero, "assistant", respuesta)
        
        # Log de uso para tracking
        print(f"[API CALL] Modelo: {modelo}, Tokens: ~{len(mensaje)//4}")
        
        return respuesta
        
    except Exception as e:
        print(f"Error consultando Claude: {e}")
        return "Disculpa, tuve un problema. ¿Podrías reformular tu pregunta?"

def enviar_whatsapp(numero, texto):
    """Envía mensaje por WhatsApp"""
    url = f"{EVOLUTION_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {
        "apikey": EVOLUTION_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "number": numero,
        "textMessage": {"text": texto}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Error enviando WhatsApp: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook que recibe mensajes de WhatsApp"""
    try:
        data = request.json
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] === WEBHOOK RECIBIDO ===")
        
        # Ignorar mensajes propios
        if data.get('data', {}).get('key', {}).get('fromMe'):
            print("[IGNORADO] Mensaje propio")
            return jsonify({"status": "ignored"})
        
        # Extraer datos
        mensaje_data = data.get('data', {})
        key = mensaje_data.get('key', {})
        message = mensaje_data.get('message', {})
        
        numero = key.get('remoteJid', '')
        texto = (
            message.get('conversation') or 
            message.get('extendedTextMessage', {}).get('text') or
            ""
        )
        
        if not texto:
            print("[IGNORADO] Sin texto")
            return jsonify({"status": "no text"})
        
        print(f"[MENSAJE] De: {numero}")
        print(f"[MENSAJE] Texto: {texto}")
        
        # Procesar con Claude (con caché y modelo inteligente)
        respuesta = consultar_claude(texto, numero)
        
        print(f"[RESPUESTA] {respuesta[:100]}...")
        
        # Enviar respuesta
        enviado = enviar_whatsapp(numero, respuesta)
        
        if enviado:
            print("[OK] Mensaje enviado")
            return jsonify({"status": "success"})
        else:
            print("[ERROR] Fallo al enviar")
            return jsonify({"status": "error"}), 500
            
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "service": "whatsapp-bot-optimized",
        "cache_entries": len(RESPUESTAS_CACHE),
        "active_conversations": len(conversaciones),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/stats', methods=['GET'])
def stats():
    """Estadísticas de uso"""
    total_mensajes = sum(len(hist) for hist in conversaciones.values())
    return jsonify({
        "conversaciones_activas": len(conversaciones),
        "total_mensajes": total_mensajes,
        "respuestas_cache": len(RESPUESTAS_CACHE)
    })

@app.route('/reset/<numero>', methods=['POST'])
def reset_conversacion(numero):
    """Resetea conversación"""
    numero_fmt = f"{numero}@s.whatsapp.net" if '@' not in numero else numero
    if numero_fmt in conversaciones:
        del conversaciones[numero_fmt]
        return jsonify({"status": "reset", "numero": numero})
    return jsonify({"status": "not found"}), 404

@app.route('/', methods=['GET'])
def home():
    """Home"""
    return """
    <html>
    <head><title>WhatsApp Bot</title></head>
    <body style="font-family: Arial; padding: 50px; text-align: center;">
        <h1>🤖 WhatsApp Bot con Claude AI</h1>
        <p>✅ Bot funcionando correctamente</p>
        <h3>Optimizaciones:</h3>
        <ul style="list-style: none;">
            <li>💾 Caché de respuestas frecuentes (0 costo)</li>
            <li>🧠 Selección inteligente de modelo</li>
            <li>💰 Haiku para preguntas simples</li>
            <li>⚡ Sonnet solo para consultas complejas</li>
        </ul>
        <p><a href="/health">Health Check</a> | <a href="/stats">Estadísticas</a></p>
    </body>
    </html>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)