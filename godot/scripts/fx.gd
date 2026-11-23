extends RefCounted
## Petits effets visuels réutilisables : matériaux lumineux, traînées, explosions.
## Tout est en primitives + CPUParticles3D pour marcher partout sans assets.


static func glow_material(color: Color, energy := 3.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = energy  # > 1 : déclenche le "glow" de l'environnement
	return m


static func _particle_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.vertex_color_use_as_albedo = true  # la couleur vient du dégradé des particules
	m.albedo_color = Color(1.6, 1.6, 1.6)  # HDR : fait briller les particules
	return m


static func _particle_mesh(radius: float) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = radius
	s.height = radius * 2.0
	s.radial_segments = 8
	s.rings = 4
	s.material = _particle_material()
	return s


static func _ramp(color: Color) -> Gradient:
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.95, 0.8, 1.0))
	g.set_color(1, Color(color.r, color.g, color.b, 0.0))
	g.add_point(0.35, color)
	return g


static func _shrink_curve() -> Curve:
	var c := Curve.new()
	c.add_point(Vector2(0.0, 1.0))
	c.add_point(Vector2(1.0, 0.0))
	return c


## Traînée à attacher à un projectile (les particules restent dans le monde).
static func trail(color: Color, size := 1.0) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount = 60
	p.lifetime = 0.5
	p.local_coords = false
	p.mesh = _particle_mesh(0.16 * size)
	p.direction = Vector3.UP
	p.spread = 180.0
	p.initial_velocity_min = 0.2
	p.initial_velocity_max = 0.9
	p.gravity = Vector3(0, 0.8, 0)
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.3
	p.scale_amount_curve = _shrink_curve()
	p.color_ramp = _ramp(color)
	return p


## Explosion : gerbe de particules + flash de lumière. Se détruit toute seule.
static func explosion(parent: Node, pos: Vector3, color: Color, size := 1.0) -> void:
	var root := Node3D.new()
	parent.add_child(root)
	root.global_position = pos

	var p := CPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 1.0
	p.amount = int(80 * size) + 10
	p.lifetime = 0.9
	p.mesh = _particle_mesh(0.2 * size)
	p.direction = Vector3.UP
	p.spread = 180.0
	p.initial_velocity_min = 2.0 * size
	p.initial_velocity_max = 6.0 * size
	p.gravity = Vector3(0, -5.0, 0)
	p.damping_min = 2.0
	p.damping_max = 4.0
	p.scale_amount_curve = _shrink_curve()
	p.color_ramp = _ramp(color)
	root.add_child(p)
	p.emitting = true

	var flash := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 0.6 * size
	s.height = 1.2 * size
	flash.mesh = s
	flash.material_override = glow_material(color.lightened(0.3), 3.0)
	flash.scale = Vector3.ONE * 0.2
	root.add_child(flash)

	var light := OmniLight3D.new()
	light.light_color = color
	light.light_energy = 3.0 * size
	light.omni_range = 5.0 * size
	root.add_child(light)

	var tw := root.create_tween().set_parallel(true)
	tw.tween_property(flash, "scale", Vector3.ONE, 0.12)
	tw.tween_property(light, "light_energy", 0.0, 0.6)
	tw.chain().tween_property(flash, "scale", Vector3.ONE * 0.01, 0.25)
	root.get_tree().create_timer(1.6).timeout.connect(root.queue_free)


## Petite gerbe d'étincelles (pose d'une carte, d'une base...).
static func burst(parent: Node, pos: Vector3, color: Color, amount := 30) -> void:
	var p := CPUParticles3D.new()
	parent.add_child(p)
	p.global_position = pos
	p.one_shot = true
	p.explosiveness = 0.9
	p.amount = amount
	p.lifetime = 0.8
	p.mesh = _particle_mesh(0.07)
	p.direction = Vector3.UP
	p.spread = 35.0
	p.initial_velocity_min = 2.0
	p.initial_velocity_max = 4.0
	p.gravity = Vector3(0, -3.0, 0)
	p.color_ramp = _ramp(color)
	p.emitting = true
	p.get_tree().create_timer(1.2).timeout.connect(p.queue_free)
