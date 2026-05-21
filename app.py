import io
import uuid
import time
import numpy as np
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components


# ==========================================
# IA
# ==========================================
from tensorflow.keras.applications.mobilenet_v2 import (
    MobileNetV2,
    preprocess_input,
    decode_predictions,
)

# ==========================================
# MQTT
# ==========================================
import paho.mqtt.client as mqtt


# =========================================================
# CONFIG MQTT
# =========================================================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

TOPIC_COMMAND = "DoorPet/command"
TOPIC_STATUS = "DoorPet/status"
TOPIC_DETECTION = "DoorPet/detection"


# =========================================================
# CONFIG STREAMLIT
# =========================================================
st.set_page_config(
    page_title="DoorPet",
    page_icon="🐾",
    layout="centered",
)

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>

.stApp{
    background-color:#F5F5F5;
}

h1,h2,h3,p{
    color:#111111;
}

.stButton button{
    border-radius:10px;
    height:50px;
    font-size:16px;
    font-weight:600;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# CARGAR MODELO IA
# =========================================================
@st.cache_resource
def load_model():
    return MobileNetV2(weights="imagenet")


model = load_model()


# =========================================================
# SESSION STATE
# =========================================================
for key, val in [
    ("door_state", "desconocido"),
    ("last_animal", "none"),
    ("log", []),
]:
    if key not in st.session_state:
        st.session_state[key] = val


# =========================================================
# FUNCION LOG
# =========================================================
def add_log(msg):
    st.session_state.log.insert(0, msg)
    st.session_state.log = st.session_state.log[:10]


# =========================================================
# MQTT CALLBACK
# =========================================================
def on_message(client, userdata, msg):

    payload = msg.payload.decode().strip().lower()

    if msg.topic == TOPIC_STATUS:

        if payload == "abierta":
            st.session_state.door_state = "abierta"

        elif payload == "cerrada":
            st.session_state.door_state = "cerrada"

    elif msg.topic == TOPIC_DETECTION:

        if payload in ("dog", "cat"):
            st.session_state.last_animal = payload


# =========================================================
# MQTT CLIENT
# =========================================================
@st.cache_resource
def get_mqtt_client():

    client = mqtt.Client(
        client_id="DoorPet_" + uuid.uuid4().hex[:6]
    )

    client.on_message = on_message

    client.connect(
        MQTT_BROKER,
        MQTT_PORT,
        60
    )

    client.subscribe(TOPIC_STATUS)
    client.subscribe(TOPIC_DETECTION)

    client.loop_start()

    return client


mqtt_client = get_mqtt_client()


# =========================================================
# ENVIAR COMANDOS MQTT
# =========================================================
def send_command(command):

    result = mqtt_client.publish(
        TOPIC_COMMAND,
        command
    )

    try:
        result.wait_for_publish()
    except:
        pass

    time.sleep(0.3)


# =========================================================
# DETECCION IA
# =========================================================
def detect_animal(image_bytes):

    try:

        img = Image.open(
            io.BytesIO(image_bytes)
        ).convert("RGB")

        img = img.resize((224, 224))

        x = preprocess_input(
            np.expand_dims(np.array(img), axis=0)
        )

        preds = decode_predictions(
            model.predict(x, verbose=0),
            top=5
        )[0]

        dog_words = [
            "dog",
            "retriever",
            "poodle",
            "terrier",
            "beagle",
            "husky",
            "bulldog",
            "labrador",
            "rottweiler",
            "doberman",
            "shepherd",
        ]

        for _, label, _ in preds:

            label = label.lower()

            if "cat" in label:
                return "cat"

            if any(w in label for w in dog_words):
                return "dog"

        return "none"

    except:
        return "none"


# =========================================================
# HEADER
# =========================================================
st.image("doorpet.png", width=180)

st.title("🐾")

st.write(
    "Sistema inteligente de control de puerta "
    "por voz + IA + MQTT"
)

st.divider()

# =========================================================
# ESTADO
# =========================================================
col1, col2 = st.columns(2)

with col1:

    st.subheader("Estado puerta")

    if st.session_state.door_state == "abierta":
        st.success("🔓 ABIERTA")

    elif st.session_state.door_state == "cerrada":
        st.error("🔒 CERRADA")

    else:
        st.info("Estado desconocido")


with col2:

    st.subheader("Última detección")

    if st.session_state.last_animal == "dog":
        st.success("🐕 Perro")

    elif st.session_state.last_animal == "cat":
        st.success("🐈 Gato")

    else:
        st.info("Sin detecciones")


st.divider()




# =========================================================
# INPUT OCULTO PARA RECIBIR TEXTO
# =========================================================
voice_text = st.text_area(
    "Comando voz",
    key="voice_command",
    height=1
)

# =========================================================
# PROCESAR COMANDO
# =========================================================
if voice_text:

    text = voice_text.lower().strip()

    st.info(f"Comando reconocido: {text}")

    # =====================================
    # ABRIR
    # =====================================
    if (
        "abrir puerta" in text
        or "abre la puerta" in text
        or "abrir" in text
        or "abre" in text
    ):

        send_command("open")

        st.session_state.door_state = "abierta"

        add_log(f"🎤 Voz → abrir ({text})")

        st.success("🔓 Puerta abierta")

        st.session_state.voice_command = ""

        st.rerun()

    # =====================================
    # CERRAR
    # =====================================
    elif (
        "cerrar puerta" in text
        or "cierra la puerta" in text
        or "cerrar" in text
        or "cierra" in text
    ):

        send_command("close")

        st.session_state.door_state = "cerrada"

        add_log(f"🎤 Voz → cerrar ({text})")

        st.success("🔒 Puerta cerrada")

        st.session_state.voice_command = ""

        st.rerun()

    else:

        st.warning("Comando no reconocido")

        st.session_state.voice_command = ""


# =========================================================
# BOTONES MANUALES
# =========================================================
st.subheader("🔘 Control manual")

col_open, col_close = st.columns(2)

with col_open:

    if st.button(
        "🔓 Abrir puerta",
        use_container_width=True
    ):

        send_command("open")

        st.session_state.door_state = "abierta"

        add_log("Botón → abrir")

        st.rerun()


with col_close:

    if st.button(
        "🔒 Cerrar puerta",
        use_container_width=True
    ):

        send_command("close")

        st.session_state.door_state = "cerrada"

        add_log("Botón → cerrar")

        st.rerun()


st.divider()


# =========================================================
# IA DETECCION
# =========================================================
st.subheader("📷 Detección de mascotas")

source = st.radio(
    "Fuente",
    ["Camara", "Subir archivo"],
    horizontal=True
)

image_bytes = None

# =========================================================
# CAMARA
# =========================================================
if source == "Camara":

    photo = st.camera_input(
        "Tomar foto"
    )

    if photo:
        image_bytes = photo.getvalue()

# =========================================================
# ARCHIVO
# =========================================================
else:

    uploaded = st.file_uploader(
        "Sube una imagen",
        type=["jpg", "jpeg", "png"]
    )

    if uploaded:
        image_bytes = uploaded.read()


# =========================================================
# MOSTRAR IMAGEN
# =========================================================
if image_bytes:

    st.image(
        image_bytes,
        width=300
    )

    if st.button(
        "🔍 Analizar con IA",
        use_container_width=True
    ):

        with st.spinner(
            "Analizando imagen..."
        ):

            animal = detect_animal(
                image_bytes
            )

        # =====================================
        # PERRO
        # =====================================
        if animal == "dog":

            st.session_state.last_animal = "dog"

            send_command("dog")

            st.success(
                "🐕 Perro detectado"
            )

            add_log("IA → perro")

        # =====================================
        # GATO
        # =====================================
        elif animal == "cat":

            st.session_state.last_animal = "cat"

            send_command("cat")

            st.success(
                "🐈 Gato detectado"
            )

            add_log("IA → gato")

        # =====================================
        # NADA
        # =====================================
        else:

            st.session_state.last_animal = "none"

            send_command("close")

            st.info(
                "No se detectó mascota"
            )

            add_log("IA → none")


st.divider()


# =========================================================
# REGISTRO
# =========================================================
st.subheader("📋 Registro")

if st.session_state.log:

    for entry in st.session_state.log:

        st.write("•", entry)

else:

    st.info("Sin actividad")


st.divider()


# =========================================================
# MQTT INFO
# =========================================================
with st.expander("⚙️ Configuración MQTT"):

    st.write("Broker:", MQTT_BROKER)
    st.write("Puerto:", MQTT_PORT)
    st.write("Topic comandos:", TOPIC_COMMAND)
    st.write("Topic estado:", TOPIC_STATUS)
    st.write("Topic detección:", TOPIC_DETECTION)
