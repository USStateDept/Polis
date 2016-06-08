-- Purge existing database to refresh schema
drop table if exists human;
drop table if exists title;
drop table if exists city;
drop table if exists human_title_xref;
drop table if exists title_city_xref;