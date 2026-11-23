extends RefCounted
## Outils pour les modèles 3D importés (fichiers .glb du dossier res://models/).
##
## Règle simple : dans un modèle, tout matériau nommé "couleur" est recoloré par le jeu
## (couleur du joueur pour les bases, couleur de la carte pour les tours et les sorts).
## Les autres matériaux (pierre, bois...) restent tels que tu les as faits dans Blender.


## Recolore les matériaux "couleur" de `node` et de tous ses enfants.
## Si le matériau brille (émission), la lumière émise prend aussi la couleur.
## Renvoie les matériaux recolorés (pour pouvoir les animer ensuite, ex. l'anneau de charge).
static func tint(node: Node, color: Color) -> Array[StandardMaterial3D]:
	var tinted: Array[StandardMaterial3D] = []
	for mesh_node in node.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = mesh_node.mesh
		for i in mesh.get_surface_count():
			var original := mesh.surface_get_material(i) as StandardMaterial3D
			if original == null or original.resource_name != "couleur":
				continue
			var mat := original.duplicate() as StandardMaterial3D  # une copie par objet : chacun sa couleur
			mat.albedo_color = color
			if mat.emission_enabled:
				mat.emission = color
			mesh_node.set_surface_override_material(i, mat)
			tinted.append(mat)
	return tinted
