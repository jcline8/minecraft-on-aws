# As recommended by Eclipse Temurin, we will build our own JRE from Java 25 using jlink.
FROM eclipse-temurin:25-jdk-alpine AS jre-build

RUN $JAVA_HOME/bin/jlink \
         --add-modules java.base,java.desktop,java.logging,java.management,java.naming,java.prefs,java.sql,java.xml,jdk.unsupported,jdk.crypto.ec,jdk.zipfs,jdk.security.auth \
         --strip-debug \
         --no-man-pages \
         --no-header-files \
         --compress=2 \
         --output /javaruntime

# Switch to alpine and add the built JRE to path.
FROM alpine:3.23.5
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
COPY --from=jre-build /javaruntime $JAVA_HOME

# Add required packages for downloading files.
RUN apk add --no-cache curl ca-certificates

# Create a dedicated non-root user and group.
RUN addgroup -g 1000 minecraft && \
    adduser -u 1000 -G minecraft -s /bin/sh -D minecraft

# Copy in the entrypoint script. 
COPY entrypoint.sh /app/entrypoint.sh

# Make the data directory, give the non-root user ownership, and make the entrypoint executable.
# These are the last commands that need to be executed as root/a sudoer.
RUN mkdir -p /data && \
    chown -R minecraft:minecraft /app /data && \
    chmod +x /app/entrypoint.sh

# Switch to the non-root user.
USER minecraft

# Use this section to download the server jar, world files, plugins, etc.
# At minimum, you're going to need the server jar. That's what's configured here.
RUN curl -o /app/paper.jar https://fill-data.papermc.io/v1/objects/bd3a58cf96874e5ea6643f5f6fe9b4f5bf9e34b795fa078c2f0ee8b98b2f907e/paper-26.2-112.jar

# Set the working directory to data where our persistent data is bind mounted to.
WORKDIR /data

# Expose custom Minecraft server port and RCON port.
EXPOSE 35132
EXPOSE 25575

# This line is for local testing only. The RCON password is stored in AWS and set as a parameter in
# when deploying the CloudFormation template.
# ENV RCON_PASSWORD=""

# Run the entrypoint script.
ENTRYPOINT ["/app/entrypoint.sh"]
# Run the server.
CMD ["java", "-Xms1G", "-Xmx1G", "-jar", "/app/paper.jar", "--nogui"]
