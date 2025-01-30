package com.sorbonne;

import org.neo4j.graphdb.*;
import org.neo4j.logging.Log;
import org.neo4j.procedure.*;

import java.util.Map;


import java.util.stream.Stream;


public class  CreateNeuron {
    // This gives us a log instance that outputs messages to the
    // standard log, normally found under `data/log/console.log`
    @Context
    public Log log;
    @Context
    public GraphDatabaseService db;


    // Exemple de base à lire completer corriger
    // Pour utiliser call nn.createNeuron("123","0","input","sotfmax")
    @Procedure(name = "nn.createNeuron",mode = Mode.WRITE)
    @Description("")
    public Stream<CreateResult> createNeuron(@Name("id") String id,
                                       @Name("layer") String layer,
                                       @Name("type") String type,
                                       @Name("activation_function") String activation_function
    ) {
        try (Transaction tx = db.beginTx()) {
            tx.execute("CREATE (n:Neuron { id: $id, layer: $layer, type: $type, bias: 0.0, " +
                            "output: null, m_bias: 0.0, v_bias: 0.0, activation_function: $activation_function })",
                    Map.of("id", id, "layer", layer, "type", type, "activation_function", activation_function));

            tx.commit();
            return Stream.of(new CreateResult("ok"));
        } catch (Exception e) {
            log.error("Error creating neuron", e);
            return Stream.of(new CreateResult("ko"));
        }
    }

        public static class CreateResult {

            public final String result;

            public CreateResult(String result) {
                this.result = result;
            }
        }
}