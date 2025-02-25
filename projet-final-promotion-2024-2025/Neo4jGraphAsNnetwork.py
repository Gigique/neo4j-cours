from pathlib import Path
from turtledemo.penrose import start

import pandas as pd
from neo4j import GraphDatabase
import math
import random
import matplotlib.pyplot as plt
import numpy as np
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Neo4jDatabaseManager:
    def __init__(self, uri, username, password, database="neuralnetwork"):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database

    def close(self):
        self.driver.close()

    def execute(self, func, *args, **kwargs):
        with self.driver.session(database=self.database) as session:
            return session.execute_write(func, *args, **kwargs)

    def execute_read(self, func, *args, **kwargs):
        with self.driver.session(database=self.database) as session:
            return session.execute_read(func, *args, **kwargs)

class NeuralNetworkManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
    @staticmethod
    def create_network(tx, network_structure, task_type, hidden_activation="relu", output_activation=None):
        #CREATE INDEX FOR(r: Row) ON(r.type, r.id);
        #CREATE INDEX FOR(n: Neuron) ON(n.type);

        start_time = time.time()  # Record the start time
        logging.info("Starting the creation of the network structure...")
        #for row_index in range(batch_size):  # Iterate over each row
        for layer_index, num_neurons in enumerate(network_structure):
            layer_type = "input" if layer_index == 0 else "output" if layer_index == len(
                network_structure) - 1 else "hidden"

            for neuron_index in range(num_neurons):
                activation_function = None

                # Assign activation function
                if layer_type == "hidden":
                    activation_function = hidden_activation  # Use user-specified or default activation
                elif layer_type == "output":
                    if output_activation:
                        activation_function = output_activation
                    else:
                        # Default to task-specific activation
                        activation_function = (
                            "softmax" if task_type == "classification" and num_neurons > 1 else
                            "sigmoid" if task_type == "classification" else
                            "linear"
                        )

                # Create the neuron in the database with a unique id per row
                # Exemple de base à lire completer corriger
                tx.run("""call nn.createNeuron($id, $layer, $type, $activation_function)""", id=f"{layer_index}-{neuron_index}", layer=layer_index, type=layer_type,
                       activation_function=activation_function)

        # Create connections between layers for the current row
        for layer_index in range(len(network_structure) - 1):
            num_neurons_current = network_structure[layer_index]
            num_neurons_next = network_structure[layer_index + 1]
            for i in range(num_neurons_current):
                for j in range(num_neurons_next):
                    weight = random.uniform(
                        -math.sqrt(6) / math.sqrt(num_neurons_current + num_neurons_next),
                        math.sqrt(6) / math.sqrt(num_neurons_current + num_neurons_next)
                    )
                    tx.run("""
                    call nn.createConnection($from_id,$to_id, $weight)
                    """, from_id=f"{layer_index}-{i}", to_id=f"{layer_index + 1}-{j}",
                           weight=weight)
        end_time = time.time()  # Record the end time
        duration = end_time - start_time  # Calculate the duration
        logging.info(f"Finished creating the network structure. Total time taken: {duration:.2f} seconds.")

    @staticmethod
    def create_inputs_row_node(tx, network_structure, batch_size):
        #tx pour la transaction
        for _index in range(batch_size):
            #pour chaque ligne dans le batch création d'un nouveau noeud Row avec id unique
            tx.run("""call nn.createInputRow($id)""", id=f"{_index}")
        layer_index,num_neurons = 0,network_structure[0]
        for row_index in range(batch_size):
            for neuron_index in range(num_neurons):
                #creation de relations entre neurones de la couche de sortie et les noeuds Row
                property_name = f"X_{row_index}_{neuron_index}"
                query = f"""call nn.createConnInputNeuronInputRow($from_id, $to_id, $inputfeatureid, $value)"""
                tx.run(query, from_id=f"{row_index}",
                       to_id=f"{layer_index}-{neuron_index}",
                       inputfeatureid=f"{row_index}_{neuron_index}",
                       value=0)
    #network_structure[1:-1]
    @staticmethod
    def create_outputs_row_node(tx, network_structure, batch_size):
        for _index in range(batch_size):
            tx.run("""
                   call nn.createOutputRow($id)
                    """, id=f"{_index}")
        layer_index, num_neurons = len(network_structure) - 1, network_structure[len(network_structure) - 1]
        for row_index in range(batch_size):
            for neuron_index in range(num_neurons):
                property_name = f"Y_{row_index}_{neuron_index}"
                query = f"""call nn.createConnOutputNeuronOutputRow($from_id, $to_id, $outputbyrowid, $value)"""

                tx.run(query, from_id=f"{layer_index}-{neuron_index}",
                       to_id=f"{row_index}", outputbyrowid=f"{row_index}_{neuron_index}",
                       value=0)


    @staticmethod
    def forward_pass(tx):
        '''MATCH (row:Row {type:'inputsRow'})-[r:CONTAINS]->(inputs:Neuron {type:'input'}) RETURN  row,r,inputs'''
        '''  MATCH (row_for_inputs:Row {type:'inputsRow'})-[inputsValue_R:CONTAINS]->
            (input:Neuron {type: 'input'})-
            [r1:CONNECTED_TO]->
            (hidden:Neuron {type: 'hidden'})-
            [r2:CONNECTED_TO]->
            (output:Neuron {type: 'output'})-[outputsValues_R:CONTAINS]->
            (row_for_outputs:Row {type:'outputsRow'})'''
        tx.run("""
        call nn.createForwardPropagation()
           
        """)




    @staticmethod
    def backward_pass_adam(tx, learning_rate, beta1, beta2, epsilon, t):
        # Step 1: Update output layer
        tx.run("""
            call nn.createOutputBackwardPass($learning_rate, $beta1, $beta2, $epsilon, $t)
        """, learning_rate=learning_rate, beta1=beta1, beta2=beta2, epsilon=epsilon, t=t)

        # Step 2: Update hidden layers
        tx.run("""
            call nn.createHiddenBackwardPass($learning_rate, $beta1, $beta2, $epsilon, $t)
        """, learning_rate=learning_rate, beta1=beta1, beta2=beta2, epsilon=epsilon, t=t)

    @staticmethod
    def compute_loss(tx, task_type):
        '''MATCH (output:Neuron {type: 'output'})<-[r:CONNECTED_TO]-(prev:Neuron)
            MATCH (output)-[outputsValues_R:CONTAINS]->(row_for_outputs:Row {type: 'outputsRow'})
            WITH DISTINCT output,r,prev,outputsValues_R,row_for_outputs'''
        if task_type == "classification":
            # Cross-Entropy Loss for classification
            result = tx.run("""
                   call nn.createLossClassification($epsilon)
                """, epsilon=1e-8)
        elif task_type == "regression":
            # Mean Squared Error (MSE) for regression
            result = tx.run("""
                    call nn.createLossRegression($epsilon)
                """, epsilon=1e-8)

        record = result.single()
        return record["loss"] if record else 0.0

    @staticmethod
    def initialize_adam_parameters(tx):
        tx.run("""
              call nn.initializeRelationAdamParameters()
            """)
        tx.run("""
                call nn.initializeNeuronAdamParameters()
            """)

    @staticmethod
    def constrain_weights(tx):
        tx.run("""
                call nn.constrainWeights()
            """)

    @staticmethod
    def evaluate_model(tx):
        result = tx.run("""
            call nn.evaluateModel()
        """)
        return {record["id"]: record["predicted"] for record in result}

    @staticmethod
    def expected_output(tx):
        result = tx.run("""
                call nn.createExpectedOutput()
            """)
        return {record["id"]: record["expected"] for record in result}

    def initialize_nn(self, network_structure, task_type, activation,batch_size=32):
        if task_type == "regression":
            self.db_manager.execute(self.create_network, network_structure, task_type, output_activation=activation)
        if task_type == "classification":
            self.db_manager.execute(self.create_network, network_structure, task_type, hidden_activation=activation)
        #print(f"Hyper parameters  network_structure{network_structure}, task_type: {task_type}, output activation_function: {activation}")
        start_time = time.time()  # Record the start time
        logging.info("Starting setting batch inputs/expecteds rows...")
        self.db_manager.execute(self.create_inputs_row_node, network_structure,batch_size)
        self.db_manager.execute(self.create_outputs_row_node, network_structure,batch_size)
        end_time = time.time()  # Record the end time
        duration = end_time - start_time  # Calculate the duration
        logging.info(
            f"Finished setting  batch inputs/expecteds rows.. Total time taken: {duration:.2f} seconds.")


    def setInputs_expectedOutputs(self,dataset):
        start_time = time.time()  # Record the start time
        logging.info("Starting setting  inputs/expecteds  values and adam parameters of the network...")
        self.db_manager.execute(self.initialize_adam_parameters)
        self.db_manager.execute(self.set_inputs, dataset)
        self.db_manager.execute(self.set_expected_outputs, dataset)
        end_time = time.time()  # Record the end time
        duration = end_time - start_time  # Calculate the duration
        logging.info(f"Finished setting  input/expected values and adam parameters of the network.. Total time taken: {duration:.2f} seconds.")


    #@staticmethod
    def set_inputs(self,tx, dataset):
        for row_index, row in enumerate(dataset):
            raw_inputs = row["inputs"]
            normalized_inputs = self.normalized(raw_inputs)
            for i, value in enumerate(normalized_inputs):
                property_name = f"X_{row_index}_{i}"
                query = f"""
                call nn.setInputs($rowid, $inputfeatureid, $inputneuronid, $value)
                """
                tx.run(query, rowid=f"{row_index}",inputfeatureid=f"{row_index}_{i}",
                       inputneuronid=f"0-{i}", value=value)
                #Old version
                '''tx.run("""
                            MATCH (n:Neuron {layer: 0, id: $id})
                            SET n.output = $value
                        """, id=f"{row_index}-0-{i}", value=value)'''

    #@staticmethod
    def set_expected_outputs(self, tx, dataset,output_layer_index=2):
        for row_index, row in enumerate(dataset):
            expected_outputs = row["expected_outputs"]
            for i, value in expected_outputs.items():
                property_name = f"expected_output_{row_index}_0"
                query = f"""
                               call nn.setExpectedOutputs($rowid, $predictedoutputid, $outputneuronid,
                               $value)
                               """
                tx.run(query, rowid=f"{row_index}", predictedoutputid=f"{row_index}_0",
                       outputneuronid=f"{output_layer_index}-0", value=value)
                '''tx.run("""
                            MATCH (n:Neuron {id: $id})
                            SET n.expected_output = $value
                        """, id=neuron_id, value=value)'''

    def train(self, dataset, learning_rate, beta1, beta2, epsilon, task_type, epoch):
        total_train_loss = 0
        self.db_manager.execute(self.forward_pass)
        loss = self.db_manager.execute(self.compute_loss, task_type)
        total_train_loss += loss
        self.db_manager.execute(self.backward_pass_adam, learning_rate, beta1, beta2, epsilon, epoch)
        self.db_manager.execute(self.constrain_weights)
        # Average loss for this epoch
        avg_train_loss = total_train_loss / len(dataset)
        print(f"Epoch {epoch},Train  Loss: {loss:.4f}, Train AVG Loss: {avg_train_loss:.4f}")
        return loss, avg_train_loss

    def train_on_single(self, case, epochs, learning_rate, beta1, beta2, epsilon, task_type):
        raw_inputs = case["inputs"]
        expected_outputs = case["expected_outputs"]

        normalized_inputs = self.normalized(raw_inputs)

        self.db_manager.execute(self.set_expected_outputs, expected_outputs)
        self.db_manager.execute(self.set_inputs, normalized_inputs)
        losses = []
        plt.ion()  # Enable interactive mode
        fig, ax = plt.subplots()
        line, = ax.plot([], [], 'b-')
        ax.set_xlim(0, epochs)
        ax.set_ylim(0, 1)  # Adjust according to your expected loss range
        ax.set_xlabel('Epoch')
        ax.set_ylabel('Loss')
        ax.set_title('Loss Curve')
        for epoch in range(1, epochs + 1):
            self.db_manager.execute(self.forward_pass)
            loss = self.db_manager.execute(self.compute_loss, task_type)
            losses.append(loss)
            self.db_manager.execute(self.backward_pass_adam, learning_rate, beta1, beta2, epsilon, epoch)
            self.db_manager.execute(self.constrain_weights)

            if (epoch + 1) % 100 == 0:
                print(f"Epoch {epoch + 1}/{epochs}, Train Loss: {loss:.4f}")

            if loss < 0.01:
                print(f"Converged at epoch {epoch}")
                break

            # Update plot dynamically
            line.set_data(range(1, len(losses) + 1), losses)
            ax.set_xlim(0, len(losses))
            ax.set_ylim(0, max(losses) + 0.1)
            plt.draw()
            plt.pause(0.01)
        plt.ioff()  # Turn off interactive mode
        plt.show()

    def validate(self, dataset, task_type,epoch):
        total_val_loss = 0
        for case_index, case in enumerate(dataset):  # Iterate through each row
            print(f"\n--- Validating Case {case_index} ---")
            raw_inputs = case["inputs"]
            expected_outputs = case["expected_outputs"]

            # Normalize and set inputs/outputs
            normalized_inputs = self.normalized(raw_inputs)
            self.db_manager.execute(self.set_expected_outputs, expected_outputs)
            self.db_manager.execute(self.set_inputs, normalized_inputs)

            # Forward pass and compute loss for this case
            self.db_manager.execute(self.forward_pass)
            loss = self.db_manager.execute(self.compute_loss, task_type)
            total_val_loss += loss
        avg_val_loss = total_val_loss / len(dataset)
        print(f"Epoch {epoch}, Validation AVG Loss: {avg_val_loss:.4f}")
        return avg_val_loss

    def validate_on_single(self, val_data, epochs,task_type):
        raw_inputs = val_data["inputs"]
        expected_outputs = val_data["expected_outputs"]

        normalized_inputs = self.normalized(raw_inputs)
        self.db_manager.execute(self.set_expected_outputs, expected_outputs)
        self.db_manager.execute(self.set_inputs, normalized_inputs)
        losses = []
        plt.ion()  # Enable interactive mode
        fig, ax = plt.subplots()
        line, = ax.plot([], [], 'b-')
        ax.set_xlim(0, epochs)
        ax.set_ylim(0, 1)  # Adjust according to your expected loss range
        ax.set_xlabel('Epoch')
        ax.set_ylabel('Loss')
        ax.set_title('Loss Curve')
        for epoch in range(1, epochs + 1):

            self.db_manager.execute(self.forward_pass)
            loss = self.db_manager.execute(self.compute_loss,task_type)
            if (epoch + 1) % 100 == 0:
                print (f"Epoch {epoch + 1}/{epochs}, Validation Loss: {loss:.4f}")
            # Update plot dynamically
            line.set_data(range(1, len(losses) + 1), losses)
            ax.set_xlim(0, len(losses))
            ax.set_ylim(0, max(losses) + 0.1)
            plt.draw()
            plt.pause(0.01)
        plt.ioff()  # Turn off interactive mode
        plt.show()

    def test(self, test_data,task_type):
        total_test_loss = 0
        for case in test_data:
            raw_inputs = case["inputs"]
            expected_outputs = case["expected_outputs"]
            normalized_inputs = self.normalized( raw_inputs)
            self.db_manager.execute(self.set_expected_outputs, expected_outputs)
            self.db_manager.execute(self.set_inputs, normalized_inputs)
            self.db_manager.execute(self.forward_pass)
            loss = self.db_manager.execute(self.compute_loss,task_type)
            total_test_loss += loss
        avg_test_loss = total_test_loss / len(test_data)
        return  avg_test_loss


    def evaluate(self):
        print("Evaluating model...")
        predictions  = self.db_manager.execute_read(self.evaluate_model)
        expecteds  = self.db_manager.execute_read(self.expected_output)
        print(f"Predictions: {predictions}")
        print(f"Expecteds: {expecteds}")
        '''print(f"Expected: {expected_outputs}")'''

    def create_batches(self, data, batch_size=128, shuffle=True):
        if shuffle:
            random.shuffle(data)
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]
    def normalized(self,input,mms=True):
        if mms:
            inputs = np.array(input)
            # Min-Max Normalization
            inputs_min = np.min(inputs)
            inputs_max = np.max(inputs)
            normalized_inputs = (inputs - inputs_min) / (inputs_max - inputs_min)
            return normalized_inputs.tolist()
        inputs_mean = np.mean(input)
        inputs_std = np.std(input)
        standardized_inputs = (input - inputs_mean) / inputs_std
        return standardized_inputs.tolist()
# ========================
# Test Code
# ========================


def generate_test_cases_from_csv(csv_file_path, input_columns, output_columns, layers_length):
    """
    Generate test cases from a CSV file.

    Args:
        csv_file_path (str): Path to the CSV file containing real-life data.
        input_columns (list): List of column names to use as inputs.
        output_columns (list): List of column names to use as expected outputs.
        layers_length (int): Length of the layers (used in output keys).

    Returns:
        list: List of test cases with inputs and expected outputs.
    """
    # Load the CSV file into a DataFrame
    df = pd.read_csv(csv_file_path)

    test_cases = []

    for row_index, row in df.iterrows():
        # Extract inputs and outputs from the row
        inputs = row[input_columns].tolist()
        outputs = row[output_columns].tolist()

        # Convert outputs into the expected format
        # Assuming binary classification for two outputs as in your original code
        '''if outputs.count(max(outputs)) > 1:  # If there's a tie
            expected_outputs = {
                f"{layers_length}-0": 0.5,
                f"{layers_length}-1": 0.5
            }
        else:
            expected_outputs = {
                f"{layers_length}-0": 1.0 if outputs.index(max(outputs)) == 0 else 0.0,
                f"{layers_length}-1": 1.0 if outputs.index(max(outputs)) == 1 else 0.0
            }'''

        expected_outputs = {}
        for output_index, output in enumerate(outputs, start=0):
            expected_outputs[f"{row_index}-{layers_length}-{output_index}"] = output
        # Append the case to the list
        test_cases.append({
            "inputs": inputs,
            "expected_outputs": expected_outputs
        })

    # Save test cases to a JSON file
    with open("test_cases.json", "w") as json_file:
        json.dump(test_cases, json_file, indent=4)

    return test_cases

# Specify the CSV file path
csv_file_path = "processed_data.csv"

# Define the input and output columns
#input_columns = ["HomeTeamId","AwayTeamId","HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR","B365H","B365D","B365A","BWH","BWD","BWA","BFH","BFD","BFA","PSH","PSD","PSA","WHH","WHD","WHA","1XBH","1XBD","1XBA","MaxH","MaxD","MaxA","AvgH","AvgD","AvgA","BFEH","BFED","BFEA","B365>2.5","B365<2.5","P>2.5","P<2.5","Max>2.5","Max<2.5","Avg>2.5","Avg<2.5","BFE>2.5","BFE<2.5","AHh","B365AHH","B365AHA","PAHH","PAHA","MaxAHH","MaxAHA","AvgAHH","AvgAHA","BFEAHH","BFEAHA","B365CH","B365CD","B365CA","BWCH","BWCD","BWCA","BFCH","BFCD","BFCA","PSCH","PSCD","PSCA","WHCH","WHCD","WHCA","1XBCH","1XBCD","1XBCA","MaxCH","MaxCD","MaxCA","AvgCH","AvgCD","AvgCA","BFECH","BFECD","BFECA","B365C>2.5","B365C<2.5","PC>2.5","PC<2.5","MaxC>2.5","MaxC<2.5","AvgC>2.5","AvgC<2.5","BFEC>2.5","BFEC<2.5","AHCh","B365CAHH","B365CAHA","PCAHH","PCAHA","MaxCAHH","MaxCAHA","AvgCAHH","AvgCAHA","BFECAHH","BFECAHA"]  # Replace with your actual input column names
input_columns = ["HS", "AS", "HF", "AF"]
#output_columns = ["FTHG","FTAG","FTR"]
output_columns = ["FTHG"]

def split_data(data, train_ratio=0.9, test_ratio=0.05, val_ratio=0.05):
    """
    Splits the input list into training, testing, and validation sets based on given ratios.
    """
    # Shuffle the data to ensure randomness
    random.shuffle(data)

    # Calculate the split indices
    total = len(data)
    train_end = int(total * train_ratio)
    test_end = train_end + int(total * test_ratio)

    # Split the data
    train_data = data[:train_end]
    test_data = data[train_end:test_end]
    val_data = data[test_end:]

    return train_data, test_data, val_data

if __name__ == "__main__":
    # Initialize database manager and neural network manager
    uri = "bolt://localhost:7687"
    username = "neo4j"
    password = "Aziza369@64!"
    database = "neuralnetwork"

    db_manager = Neo4jDatabaseManager(uri, username, password, database)
    nn_manager = NeuralNetworkManager(db_manager)

    try:
        # Training Parameters

        network_structure = [4, 6, 1]
        hidden_activation = "relu" # tanh,relu
        output_activation = "linear"  #Softmax Or "sigmoid" for binary classification
        task_type = "regression" #Regression or classification

        epochs = 100
        learning_rate = 0.01
        beta1 = 0.9
        beta2 = 0.999
        epsilon = 1e-8
        batch_size=4

        # Generate 1000 test cases
        file_path = Path("test_cases.json")
        if not file_path.exists():
            #_data = generate_test_cases(1000, len(network_structure)-1)
            test_cases = generate_test_cases_from_csv(csv_file_path, input_columns, output_columns, len(network_structure)-1)
            print(test_cases[0])

        with open("test_cases.json", "r") as json_file:
            test_cases = json.load(json_file)
        train_data, test_data, val_data = split_data(test_cases)
        # Step 1: Initialize
        nn_manager.initialize_nn(network_structure, task_type,output_activation,batch_size)
        losses = []
        val_losses = []
        total_train_loss=0
        #for batch in nn_manager.create_batches(train_data, batch_size):
        nn_manager.setInputs_expectedOutputs(train_data)
        for epoch in range(1, epochs + 1):
            loss, avg_train_loss = nn_manager.train(train_data, learning_rate=learning_rate, beta1=beta1, beta2=beta2, epsilon=epsilon, task_type=task_type,epoch=epoch)
            losses.append(loss)
            #val_losses.append(avg_train_loss)
            #Validation
            #val_loss = nn_manager.validate(val_data, task_type,epoch)
            #val_losses.append(val_loss)
            '''if val_loss < 0.01:
                print(f"Converged at epoch {epoch}")
                break'''
        plt.plot(range(1, len(losses) + 1), losses, label='Training Loss', color='blue')
        # plt.plot(range(1, len(val_losses) + 1), val_losses, label='Validation Loss', color='orange')
        plt.xlabel('Epoch')
        plt.ylabel('Average Loss')
        plt.title('Training and Validation Loss Curve')
        plt.legend()  # Add legend to differentiate between the curves
        plt.show()
        # Testing
        print("\n--- Final Testing ---")
    # test_loss =nn_manager.test(test_data, task_type)
    # Plot the final aggregated loss curve


    finally:
        # Close the database connection
        db_manager.close()
