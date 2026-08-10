USE tienda;

SELECT p.nombre, p.precio, f.nombre
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id;

SELECT p.nombre, p.precio, f.nombre
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
ORDER BY f.nombre;

SELECT p.id, p.nombre, f.id, f.nombre
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id;

SELECT p.nombre, p.precio, f.nombre
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
ORDER BY p.precio
LIMIT 1;

SELECT p.nombre, p.precio, f.nombre
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
ORDER BY p.precio DESC
LIMIT 1;

SELECT p.*
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Lenovo';

SELECT p.*
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Crucial' AND p.precio > 200;

SELECT p.*
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Asus'
OR f.nombre = 'Hewlett-Packard'
OR f.nombre = 'Seagate';

SELECT p.*
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre IN ('Asus','Hewlett-Packard','Seagate');

SELECT p.nombre, p.precio
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre LIKE '%e';

SELECT p.nombre, p.precio
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre LIKE '%w%';

SELECT p.nombre, p.precio, f.nombre
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE p.precio >= 180
ORDER BY p.precio DESC, p.nombre;

SELECT DISTINCT f.id, f.nombre
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante;

SELECT f.nombre, p.nombre
FROM fabricante f
LEFT JOIN producto p ON f.id = p.id_fabricante;

SELECT f.nombre
FROM fabricante f
LEFT JOIN producto p ON f.id = p.id_fabricante
WHERE p.id IS NULL;

SELECT COUNT(*) FROM producto;

SELECT COUNT(*) FROM fabricante;

SELECT COUNT(DISTINCT id_fabricante) FROM producto;

SELECT AVG(precio) FROM producto;

SELECT MIN(precio) FROM producto;

SELECT MAX(precio) FROM producto;

SELECT nombre, precio FROM producto ORDER BY precio LIMIT 1;

SELECT nombre, precio FROM producto ORDER BY precio DESC LIMIT 1;

SELECT SUM(precio) FROM producto;

SELECT COUNT(*)
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Asus';

SELECT AVG(p.precio)
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Asus';

SELECT MIN(p.precio)
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Asus';

SELECT MAX(p.precio)
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Asus';

SELECT SUM(p.precio)
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Asus';

SELECT MAX(p.precio), MIN(p.precio), AVG(p.precio), COUNT(*)
FROM producto p
JOIN fabricante f ON p.id_fabricante = f.id
WHERE f.nombre = 'Crucial';

SELECT f.nombre, COUNT(p.id)
FROM fabricante f
LEFT JOIN producto p ON f.id = p.id_fabricante
GROUP BY f.nombre
ORDER BY COUNT(p.id) DESC;

SELECT f.nombre, MAX(p.precio), MIN(p.precio), AVG(p.precio)
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante
GROUP BY f.nombre;

SELECT id_fabricante, MAX(precio), MIN(precio), AVG(precio), COUNT(*)
FROM producto
GROUP BY id_fabricante
HAVING AVG(precio) > 200;

SELECT f.nombre, MAX(p.precio), MIN(p.precio), AVG(p.precio), COUNT(*)
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante
GROUP BY f.nombre
HAVING AVG(p.precio) > 200;

SELECT COUNT(*) FROM producto WHERE precio >= 180;

SELECT id_fabricante, COUNT(*)
FROM producto
WHERE precio >= 180
GROUP BY id_fabricante;

SELECT id_fabricante, AVG(precio)
FROM producto
GROUP BY id_fabricante;

SELECT f.nombre, AVG(p.precio)
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante
GROUP BY f.nombre;

SELECT f.nombre
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante
GROUP BY f.nombre
HAVING AVG(p.precio) >= 150;

SELECT f.nombre
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante
GROUP BY f.nombre
HAVING COUNT(*) >= 2;

SELECT f.nombre, COUNT(p.id)
FROM fabricante f
JOIN producto p ON f.id = p.id_fabricante
WHERE p.precio >= 220
GROUP BY f.nombre;