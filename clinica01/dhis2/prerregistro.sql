-- Base de los formularios de prerregistro (R8, D-07, apps#6). Idempotente:
-- se puede ejecutar las veces que haga falta. La corre el rol dhis2 como el
-- usuario dueño del contenedor, con -v clave=<contraseña de formularios> y
-- -v clave_consultas=<contraseña de consultas>.

SELECT 'CREATE DATABASE prerregistro'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'prerregistro')\gexec

DO $$
BEGIN
  -- Dueño de la tabla, sin login
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'prerregistro_dueno') THEN
    CREATE ROLE prerregistro_dueno NOLOGIN;
  END IF;
  -- La app de comunidad01: solo INSERT
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'formularios') THEN
    CREATE ROLE formularios LOGIN;
  END IF;
  -- La consulta de clinica01 (apps#7): lee y marca atendido
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'consultas') THEN
    CREATE ROLE consultas LOGIN;
  END IF;
END
$$;

ALTER ROLE formularios WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 10 PASSWORD :'clave';
ALTER ROLE consultas WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 10 PASSWORD :'clave_consultas';

REVOKE ALL ON DATABASE prerregistro FROM PUBLIC;
GRANT CONNECT ON DATABASE prerregistro TO formularios, consultas;

\connect prerregistro

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO formularios, consultas;

CREATE TABLE IF NOT EXISTS prerregistros (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  creado           timestamptz NOT NULL DEFAULT now(),
  codigo           text NOT NULL CHECK (codigo ~ '^[A-Z0-9]{4}$'),
  nombres          text NOT NULL CHECK (length(nombres) BETWEEN 1 AND 80),
  apellidos        text NOT NULL CHECK (length(apellidos) BETWEEN 1 AND 80),
  tipo_documento   text NOT NULL CHECK (tipo_documento IN ('CC', 'TI', 'RC', 'CE', 'OTRO', 'NINGUNO')),
  numero_documento text CHECK (length(numero_documento) <= 20),
  fecha_nacimiento date CHECK (fecha_nacimiento >= DATE '1900-01-01'),
  celular          text CHECK (celular ~ '^[0-9]{7,15}$'),
  motivo           text NOT NULL CHECK (motivo IN ('CONTROL', 'FIEBRE', 'DOLOR', 'EMBARAZO', 'VACUNACION', 'OTRO')),
  detalle          text CHECK (length(detalle) <= 200),
  autoriza_datos   boolean NOT NULL CHECK (autoriza_datos),
  -- Lo marca el personal desde la consulta (apps#7)
  atendido         boolean NOT NULL DEFAULT false
);
ALTER TABLE prerregistros OWNER TO prerregistro_dueno;
-- Cuándo se marcó atendido, para la lista "Atendidos hoy" de la consulta (apps#7)
ALTER TABLE prerregistros ADD COLUMN IF NOT EXISTS atendido_en timestamptz;

-- formularios solo inserta: no lee, no cambia ni borra (la identidad no
-- necesita permisos sobre su secuencia)
REVOKE ALL ON prerregistros FROM PUBLIC, formularios, consultas;
GRANT INSERT ON prerregistros TO formularios;

-- consultas lee y solo puede cambiar atendido y atendido_en (no inserta ni borra)
GRANT SELECT, UPDATE (atendido, atendido_en) ON prerregistros TO consultas;
