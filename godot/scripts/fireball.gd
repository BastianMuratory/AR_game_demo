extends Node3D
## Boule de feu : avance tout droit, explose sur une base adverse ou en sortant du plateau.
## Le modèle 3D est dans models/boule_de_feu.glb, la scène (modèle + lumière) dans scenes/boule_de_feu.tscn.

const Models := preload("res://scripts/models.gd")
const FX := preload("res://scripts/fx.gd")

var direction := Vector3.RIGHT
var speed := 7.0
var damage := 20
var owner_player := 0
var color := Color(1.0, 0.45, 0.1)
var game: Node  # main.gd, pour connaître les forteresses et les limites du plateau

var _age := 0.0  # secondes depuis le lancement
var _trail: CPUParticles3D


func _ready() -> void:
	Models.tint($Modele, color.lightened(0.35))
	$Lumiere.light_color = color
	_trail = FX.trail(color)  # traînée de particules (effet, pas un modèle)
	add_child(_trail)


func _process(delta: float) -> void:
	_age += delta
	position += direction * speed * delta
	position.y = 0.7 + sin(_age * 14.0) * 0.05  # petit flottement

	# Touche une base adverse ?
	for f in game.fortresses:
		if f.player == owner_player or not f.is_target():
			continue
		var d := Vector2(position.x - f.position.x, position.z - f.position.z).length()
		if d < f.radius:
			f.take_damage(damage)
			_explode(1.0)
			return

	# Sortie du plateau (ou trop vieille) ?
	if game.is_outside(position) or _age > 6.0:
		_explode(0.5)  # raté : petite explosion au bord du plateau


func _explode(size: float) -> void:
	FX.explosion(get_parent(), global_position, color, size)
	# on laisse la traînée finir de s'éteindre au lieu de la couper net
	_trail.emitting = false
	_trail.reparent(get_parent())
	_trail.get_tree().create_timer(_trail.lifetime + 0.1).timeout.connect(_trail.queue_free)
	queue_free()
