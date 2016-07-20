Ansible modules
================================

This is a collection of modules written internally at mnubo for use with our infrastructure stack. In the next few lines we'll highlight what's available and how to use them. We've included a requirements file for our modules in the library directory.


k8s_secret
--------------------------------------------------------------------

A module to manage kubernetes secrets. Pretty useful when using private registries so Kubernetes can pull volumes by itself. Basic example:

      k8s_secret:
        config:
            api_host: "localhost:8888"
            namespace: "default"
        name: "my_registry"
        definition:
          secret_type: "dockercfg"
          data: '{"private-registry.example.com":{"auth":"erHyHVWyTgRbCLpKgXPdXYFxKNzEZGhRfGvcQ4o9c4pjvTchmk", "email":"secret@example.com"}}'
        state: "present"

See module code for more documentation.


k8s_pod
--------------------------------------------------------------------

A module to manage kubernetes pods. Basic example:

    - name: Create a simple pod
      k8s_pod:
      config:
          api_host: "localhost:8888"
          namespace: "default"
          pull_secret: "my_registry"
      name: "myweb"
      spec:
          containers:
              - name: "myweb"
                image: "httpd:2.4"
                ports:
                  - containerPort: 80
                    name: "http"
                    protocol: "TCP"
                env:
                  MY_VAR: "some_value"
                volumes:
                  - name: "my_volume"
                    mount_path: "/data/html"
                    read_only: False
          volumes:
              - type: "host"
                name: "my_volume"
                path: "/data/myweb/html"
      state: "present"

See module code for more documentation.

**Notes:** We need to improve error management at the kubernetes-py layer and bubble-up the errors to an ansible output variable.

k8s_rc
--------------------------------------------------------------------

A module to manage kubernetes replication controllers. If anything changed, it will perform a rolling restart of the replication controller. Basic example:


    k8s_rc:
      config:
          api_host: "localhost:8888"
          namespace: "default"
          pull_secret: "my_registry"
      name: "myweb"
      pod:
          containers:
              - name: "myweb"
                image: "httpd:2.4"
                ports:
                  - containerPort: 80
                    name: "http"
                    protocol: "TCP"
                env:
                  MY_VAR: "some_value"
                volumes:
                  - name: "my_volume"
                    mount_path: "/data/html"
                    read_only: False
          volumes:
              - type: "host"
                name: "my_volume"
                path: "/data/myweb/html"
      replicas: 2
      state: "present"

See module code for more documentation.

**Notes:** Rolling restarts have default variables. Please see the module documention in the code for more information. We need to improve error management at the kubernetes-py layer and bubble-up the errors to an ansible output variable.

k8s_service
--------------------------------------------------------------------

A module to manage kubernetes services. Here's a basic example:

      k8s_service:
        config:
            api_host: "localhost:8888"
            namespace: "default"
        name: "myweb"
        definition:
          service_type: "NodePort"
          ports:
            - port: 80
              target_port: "http"
              protocol: "TCP"
              node_port: 8030
          selector:
            name: "myweb"
          cluster_ip: "10.100.200.10"
        state: "present"

See module code for more documentation.

**Notes:** The module is set to retry for a while. We need to improve error management at the kubernetes-py layer and bubble-up the errors to an ansible output variable.
