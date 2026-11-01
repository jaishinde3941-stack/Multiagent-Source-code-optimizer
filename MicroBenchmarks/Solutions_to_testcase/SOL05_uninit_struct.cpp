// Category: Uninitialized Variables (Success Case)
// Expected Result: Struct members should be initialized

#include <iostream>

struct Point {
    int x = 0;  // SUCCESS: Default initialization
    int y = 0;
};

int main() {
    Point p;
    
    int distance = p.x * p.x + p.y * p.y;
    std::cout << "Distance squared: " << distance << std::endl;
    
    return 0;
}
