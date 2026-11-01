// Category: Resource Leaks
// Error: Resource leak in exception path

#include <iostream>
#include <stdexcept>

void riskyOperation() {
    throw std::runtime_error("Something went wrong");
}

int main() {
    int* data = new int[50];
    
    try {
        riskyOperation();  // ERROR: Exception thrown, data never freed
    } catch (const std::exception& e) {
        std::cout << "Error: " << e.what() << std::endl;
        return 1;  // Memory leaked
    }
    
    delete[] data;
    return 0;
}
