FROM cm2network/steamcmd:latest
#FROM gcr.io/distroless/cc-debian13:latest-arm64

# Expose the port that the dedicated server listens on
EXPOSE 7777/udp
EXPOSE 27015/udp

ENV SERVERDIR="/server"

COPY . $${SERVERDIR}

ENTRYPOINT [ "/bin/bash", "$tpl_executable" ]
