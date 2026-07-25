FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /adam-bus .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=builder /adam-bus /adam-bus
EXPOSE 4222 8086
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://localhost:8086/api/health || exit 1
CMD ["/adam-bus"]

