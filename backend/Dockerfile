FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY pom.xml ./
COPY src ./src
RUN --mount=type=cache,target=/root/.m2,sharing=locked \
    mvn -B -ntp \
      -Daether.transport.http.connectTimeout=10000 \
      -Daether.transport.http.requestTimeout=120000 \
      -Daether.transport.http.retryHandler.count=3 \
      verify

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN addgroup --system supportflow && adduser --system --ingroup supportflow supportflow
COPY --from=build /workspace/target/supportflow-backend-0.0.1-SNAPSHOT.jar app.jar
USER supportflow
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
