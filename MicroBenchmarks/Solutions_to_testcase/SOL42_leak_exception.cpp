// Category: Resource Leaks (Success Case)
// Expected Result: Use RAII or ensure cleanup in catch blocks

#include <iostream>
#include <stdexcept>
#include <vector>

void riskyOperation() {
    throw std::runtime_error("Something went wrong");
}

int main() {
    // SUCCESS: Used std::vector (RAII) which cleans up automatically even on exceptions
    try {
        std::vector<int> data(50);
        riskyOperation();
    } catch (const std::exception& e) {
        std::cout << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
