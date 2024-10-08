# LOCAL-URL-SHORTENER

A simple URL shortener that uses a local database to store the shortened URLs.

## Architecture

- **API**: FastAPI
- **Database**: SQLite
- **Cache**: Redis
- **Load Balancer**: Nginx

all deployed using Docker

## Setup

1. Clone the repository
2. Run `docker-compose up --build` to build and run the services
3. The API will be available at `http://localhost:19000`


## Endpoints

### POST /v1/shorten

```bash
curl -X POST "http://localhost:19000/v1/shorten" -H "Content-Type: application/json" -d '{"url": "https://www.google.com"}'
```

Response:

```json
{
  "shortened_url": "http://localhost:19000/5cb54051"
}
```

### GET /{shortened_url}

```bash
curl -X GET "http://localhost:19000/5cb54051"
```

Redirects to the original URL


