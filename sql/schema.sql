-- create table for people
create table person (
  id integer primary key autoincrement,
  pid text not null,
  fname text not null,
  lname text not null,
  name text not null,
  title text not null,
  twitter text,
  url text
);

-- create table for cities
create table city (
  id integer primary key autoincrement,
  cid text not null,
  city text not null,
  state text not null,
  country text not null,
  population integer,
  url text,
  twitter text
);

-- link person to city, and specify date range of association
create table person_city_xref (
  pid text not null,
  cid text not null,
  start_date date not null,
  end_date date
);

-- ingest categorized content from mongo db
drop table if exists cat_content;
create table cat_content (
  _source text not null,
  uname text,
  record_id text not null,
  document text not null,
  link text not null,
  _date text not null,
  nlp_score real not null,
  nlp_cat text,
  nlp_warn text,
  primary key (_source, record_id)
);
