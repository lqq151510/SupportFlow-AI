FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src src
RUN mvn -B -q verify

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN addgroup --system supportflow && adduser --system --ingroup supportflow supportflow
COPY --from=build /workspace/target/supportflow-backend-0.0.1-SNAPSHOT.jar app.jar
USER supportflow
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
