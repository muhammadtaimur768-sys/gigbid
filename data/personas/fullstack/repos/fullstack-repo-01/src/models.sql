CREATE TABLE orders (
  id uuid PRIMARY KEY,
  user_id uuid REFERENCES users(id),
  total_cents integer NOT NULL
);
