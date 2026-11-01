// Category: Resource Leaks (Success Case)
// Expected Result: Free memory on all exit paths (or use smart pointers)

#include <iostream>

int process(int value) {
    int* buffer = new int[100];
    
    if (value < 0) {
        delete[] buffer;  // SUCCESS: Freed before early return
        return -1;
    }
    
    buffer[0] = value;
    int result = buffer[0] * 2;
    
    delete[] buffer;
    return result;
}

int main() {
    int result = process(-5);
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
