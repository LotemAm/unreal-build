FROM cm2network/steamcmd:latest

# Expose the port that the dedicated server listens on
EXPOSE 7777/udp
EXPOSE 27015/udp

ENV SERVERDIR="/server"

COPY --chown=${USER} . ${SERVERDIR}
COPY docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT [ "bash", "/docker-entrypoint.sh" ]
