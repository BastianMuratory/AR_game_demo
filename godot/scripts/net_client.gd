extends Node
## Client WebSocket vers tracker.py.
## Reçoit deux types de messages : l'état des cartes (texte JSON) et l'image du plateau (JPEG binaire).
## Se reconnecte tout seul si le tracker est relancé.

signal state_received(state: Dictionary)   # un nouvel état (cartes, plateau, caméra)
signal frame_received(image: Image)        # une nouvelle image de la caméra
signal connection_changed(online: bool)

@export var url := "ws://127.0.0.1:8765"

var connected := false
var _ws: WebSocketPeer
var _retry_in := 0.0  # secondes avant de retenter une connexion


## Appelé à chaque image : on lit ce qui est arrivé, ou on retente de se connecter.
func _process(delta: float) -> void:
	if _ws == null:
		_retry_in -= delta
		if _retry_in <= 0.0:
			_open()
		return

	_ws.poll()  # fait avancer la connexion (obligatoire à chaque image)
	match _ws.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not connected:
				connected = true
				connection_changed.emit(true)
			_read_packets()
		WebSocketPeer.STATE_CLOSED:
			if connected:
				connected = false
				connection_changed.emit(false)
			_ws = null
			_retry_in = 1.0


func _open() -> void:
	_ws = WebSocketPeer.new()
	# Les images JPEG dépassent largement le tampon par défaut (64 Ko).
	_ws.inbound_buffer_size = 4 * 1024 * 1024
	if _ws.connect_to_url(url) != OK:
		_ws = null
		_retry_in = 1.0


## Lit tous les messages arrivés depuis la dernière image.
func _read_packets() -> void:
	var last_jpeg := PackedByteArray()
	while _ws.get_available_packet_count() > 0:
		var pkt := _ws.get_packet()
		if _ws.was_string_packet():
			var data = JSON.parse_string(pkt.get_string_from_utf8())
			if data is Dictionary:
				state_received.emit(data)
		else:
			last_jpeg = pkt  # s'il y a du retard, on ne décode que l'image la plus récente
	if not last_jpeg.is_empty():
		var img := Image.new()
		if img.load_jpg_from_buffer(last_jpeg) == OK:
			frame_received.emit(img)
